"""Controle RGB 1x/4x/A2C no processo Vulkan descartável da CI.

Só é copiado para plugins durante o teste; não modifica produção.
A máscara renderAlphaMask NÃO participa, pois desliga MSAA no legado.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

from PyQt5 import QtCore
from core import G


def load(app):
    destino = Path(os.environ["MAKEHUMANO_HARNESS_FORMATO_JSON"])
    png = Path(os.environ["MAKEHUMANO_HARNESS_FORMATO_PNG"])
    provisorio = destino.with_name(destino.stem + "-observacao.json")
    pasta = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if pasta not in sys.path:
        sys.path.insert(0, pasta)

    from observar_formato_cena_vulkan import observar_captura_offscreen
    from configurar_camera_paridade import fixar_camera, manifesto_camera
    from diagnosticar_a2c_msaa import (
        CONTROLES, comparar_rgb, metadados_rgb, validar_controles,
    )
    from textura_alpha_controle import salvar_textura_alfa_parcial

    iniciado = False

    def medir():
        nonlocal iniciado
        if iniciado:
            return
        if not getattr(app, "_startup_complete", False):
            QtCore.QTimer.singleShot(200, medir)
            return
        iniciado = True
        cena = None
        material = None
        originais = {}
        amostras_originais = None
        try:
            import numpy as np
            from image import Image
            from getpath import getSysDataPath
            import vulkan_scene as modulo_vulkan
            from vulkan_scene import alpha_to_coverage_vulkan, objeto_translucido_vulkan

            cena = G.canvas._garantir_cena()
            material = app.selectedHuman.material
            originais = {
                "shader": material.shader,
                "textura": material.diffuseTexture,
                "diffuse": bool(material.shaderConfig.get("diffuse", False)),
                "opacity": float(material.opacity),
                "transparent": bool(material.transparent),
                "a2c": bool(material.alphaToCoverage),
                "recebe_sombras": bool(getattr(material, "receiveShadows", True)),
            }
            amostras_originais = int(cena.amostras)
            camera = fixar_camera(app)
            parametros_camera = manifesto_camera(camera)
            corpo_candidatos = [
                obj for obj in G.world
                if getattr(obj, "material", None) is material
                and getattr(obj, "visibility", True)
                and getattr(obj, "solid", True)
            ]
            if not corpo_candidatos:
                raise RuntimeError("Corpo original não encontrado")
            corpo = max(corpo_candidatos, key=lambda obj: len(obj.primitives))
            if int(corpo.nTransparentPrimitives) != 0:
                raise RuntimeError("Controle requer corpo com zero primitivas transparentes")

            textura_path, textura_meta = salvar_textura_alfa_parcial(
                destino.with_name(destino.stem + "-a2c-textura.png"), alfa=128
            )
            material.shader = getSysDataPath("shaders/glsl/phong")
            material.diffuseTexture = textura_path
            material.configureShading(diffuse=True)
            material.opacity = 1.0
            material.transparent = True
            material.alphaToCoverage = False
            if not bool(corpo.isTextured):
                raise RuntimeError("Material Phong não ativou a textura DIFFUSE")

            registros = {}
            imagens = {}
            texturas_varredura = {128: (textura_path, textura_meta)}

            def capturar(nome, *, amostras, transparencia, a2c,
                         sem_blend=False, escrever_z=False, alfa_textura=128,
                         sem_sombras=False):
                if alfa_textura not in texturas_varredura:
                    texturas_varredura[alfa_textura] = salvar_textura_alfa_parcial(
                        destino.with_name(
                            destino.stem + "-a2c-textura-a" + str(alfa_textura) + ".png"
                        ), alfa=alfa_textura,
                    )
                material.diffuseTexture = texturas_varredura[alfa_textura][0]
                material.transparent = transparencia
                material.alphaToCoverage = a2c
                cena.configurar_multisampling(amostras == 4)
                esperado = bool(alpha_to_coverage_vulkan(corpo, cena.amostras))
                if escrever_z and esperado:
                    raise RuntimeError("Controle Z só aceita A2C desligado")
                observado = []
                # Fora de produção: o pipeline só lê estes atributos para criar
                # variantes. Restauramos cache/estados após cada captura.
                blend_original = cena._blend_malhas
                cache_original = cena._pipelines_malhas
                raster_original = modulo_vulkan.configuracao_raster_vulkan
                if sem_blend:
                    cena._blend_malhas = None
                if escrever_z:
                    def raster_ensaio(obj, *, linhas=False):
                        config = raster_original(obj, linhas=linhas)
                        if obj is corpo and not linhas:
                            return config[0], True, config[2]
                        return config
                    modulo_vulkan.configuracao_raster_vulkan = raster_ensaio
                if sem_blend or escrever_z:
                    # Sem cache limpo a chave de baseline pode reutilizar
                    # um pipeline antigo com blend habilitado.
                    cena._pipelines_malhas = {}
                # Instrumentação local: registra a chamada REAL do corpo ao pipeline.
                original = cena._pipeline_objeto
                anterior = cena.__dict__.get("_pipeline_objeto", None)
                existia = "_pipeline_objeto" in cena.__dict__

                def espionar(obj, linhas, *, pontos=False):
                    if obj is corpo:
                        observado.append({
                            "a2c_calculado": bool(alpha_to_coverage_vulkan(
                                obj, cena.amostras, linhas=bool(linhas or pontos)
                            )),
                            "recebe_sombras_material_observado": bool(
                                getattr(obj.material, "receiveShadows", True)
                            ),
                            "amostras": int(cena.amostras),
                            "linhas": bool(linhas),
                            "pontos": bool(pontos),
                            "blend_habilitado_previsto": bool(
                                cena._blend_malhas is not None
                                and not alpha_to_coverage_vulkan(
                                    obj, cena.amostras, linhas=bool(linhas or pontos)
                                )
                            ),
                            "escrita_z_prevista": bool(
                                raster_original(obj, linhas=bool(linhas or pontos))[1]
                                or escrever_z or alpha_to_coverage_vulkan(
                                    obj, cena.amostras, linhas=bool(linhas or pontos)
                                )
                            ),
                        })
                    return original(obj, linhas, pontos=pontos)

                cena._pipeline_objeto = espionar
                sombras_original = bool(
                    getattr(material, "receiveShadows", True)
                )
                if sem_sombras:
                    material.receiveShadows = False
                try:
                    rgb = cena.capturar_framebuffer(
                        [corpo], G.cameras, 1024, 768,
                        incluir_alfa=False, cor_fundo=(0.5, 0.5, 0.5, 1.0),
                    )
                finally:
                    material.receiveShadows = sombras_original
                    if existia:
                        cena._pipeline_objeto = anterior
                    else:
                        del cena._pipeline_objeto
                    # Captura a chave e depois restaura cache/override
                    # sem reutilizar pipelines forçados na GUI.
                    chaves_da_captura = list(cena._pipelines_malhas)
                    cena._pipelines_malhas = cache_original
                    cena._blend_malhas = blend_original
                    modulo_vulkan.configuracao_raster_vulkan = raster_original

                if not observado:
                    raise RuntimeError("A malha do corpo não atravessou o pipeline")
                if any(v["a2c_calculado"] != esperado for v in observado):
                    raise RuntimeError("Caminho de A2C inconsistente na malha")
                if any(
                    v["recebe_sombras_material_observado"] is not (
                        sombras_original and not sem_sombras
                    ) for v in observado
                ):
                    raise RuntimeError("Material receiveShadows inesperado na GPU")
                chaves = [
                    k for k in chaves_da_captura
                    if isinstance(k, tuple) and len(k) >= 4
                    and k[:4] == (amostras, esperado, False, False)
                ]
                if not chaves:
                    raise RuntimeError("Pipeline real não foi registrado no cache")
                blend_esperado = not (esperado or sem_blend)
                z_esperado = bool(raster_original(corpo, linhas=False)[1]
                                   or esperado or escrever_z)
                if any(v["blend_habilitado_previsto"] != blend_esperado
                       or v["escrita_z_prevista"] != z_esperado
                       for v in observado):
                    raise RuntimeError("Diagnóstico GPU Vulkan difere dos estados ensaiados")
                if escrever_z and not any(k[6] is True for k in chaves if len(k) > 6):
                    raise RuntimeError("Não houve variante de pipeline com escrita Z")
                rgb = np.ascontiguousarray(rgb)
                meta = metadados_rgb(rgb)
                saida = png if nome == "1x_sem_a2c" else png.with_name(
                    png.stem + "-" + nome + ".png"
                )
                Image(data=rgb).save(str(saida))
                registros[nome] = {
                    **meta,
                    "captura_rgb": True,
                    "amostras": int(cena.amostras),
                    "a2c_flag_material": bool(a2c),
                    "controle_blend_desligado": bool(sem_blend),
                    "controle_escrita_z_forcada": bool(escrever_z),
                    "controle_sombras_desligadas": bool(sem_sombras),
                    "recebe_sombras_material_observado": bool(
                        sombras_original and not sem_sombras
                    ),
                    "blend_habilitado_observado": bool(blend_esperado),
                    "escrita_z_observada": bool(z_esperado),
                    "material_transparent": bool(transparencia),
                    "opacity": float(material.opacity),
                    "alfa_textura": int(alfa_textura),
                    "sha256_textura_png": texturas_varredura[alfa_textura][1]["sha256_png"],
                    "nTransparentPrimitives": int(corpo.nTransparentPrimitives),
                    "classificado_translucido": bool(objeto_translucido_vulkan(corpo)),
                    "a2c_elegivel": esperado,
                    "pipeline_a2c_observado": bool(observado[-1]["a2c_calculado"]),
                    "pipeline_chave_cache_confirmada": True,
                    "rastros_pipeline_corpo": observado,
                    "arquivo_rgb": str(saida),
                    "sha256_png": hashlib.sha256(saida.read_bytes()).hexdigest(),
                }
                imagens[nome] = rgb

            with observar_captura_offscreen(cena, provisorio):
                capturar("1x_sem_a2c", amostras=1, transparencia=True, a2c=False)

                # Prova de suporte: testar AMBOS os attachments usados pelo renderer.
                suporte = {"amostras_requeridas": 4, "disponivel": False}
                try:
                    uso = cena.wgpu.TextureUsage.RENDER_ATTACHMENT
                    textura_cor = cena.device.create_texture(
                        size=(8, 8, 1), format=cena.formato,
                        sample_count=4, usage=uso,
                    )
                    textura_depth = cena.device.create_texture(
                        size=(8, 8, 1), format="depth24plus",
                        sample_count=4, usage=uso,
                    )
                    suporte["disponivel"] = bool(textura_cor and textura_depth)
                except Exception as exc:
                    suporte["erro_probe"] = f"{type(exc).__name__}: {exc}"

                if suporte["disponivel"]:
                    capturar("4x_sem_a2c", amostras=4, transparencia=True, a2c=False)
                    capturar("4x_com_a2c", amostras=4, transparencia=True, a2c=True)
                    capturar("4x_inelegivel", amostras=4, transparencia=False, a2c=True)
                    capturar("4x_sem_a2c_sem_blend_sem_z",
                             amostras=4, transparencia=True, a2c=False,
                             sem_blend=True)
                    capturar("4x_sem_a2c_sem_blend_com_z",
                             amostras=4, transparencia=True, a2c=False,
                             sem_blend=True, escrever_z=True)
                    for alfa in (64, 192):
                        capturar("4x_a%03d_sem_a2c_sem_blend_com_z" % alfa,
                                 amostras=4, transparencia=True, a2c=False,
                                 sem_blend=True, escrever_z=True, alfa_textura=alfa)
                        capturar("4x_a%03d_com_a2c" % alfa,
                                 amostras=4, transparencia=True, a2c=True,
                                 alfa_textura=alfa)
                    capturar("4x_a128_repeticao_sem_a2c_sem_blend_com_z",
                             amostras=4, transparencia=True, a2c=False,
                             sem_blend=True, escrever_z=True, alfa_textura=128)
                    # Prova causal: a configuração de receiveShadows é
                    # desligada SÓ DURANTE o draw, sem alterar o shader.
                    for alfa in (64, 128, 192):
                        capturar(f"4x_a{alfa:03d}_sem_a2c_sem_blend_com_z_sem_sombras",
                                 amostras=4, transparencia=True, a2c=False,
                                 sem_blend=True, escrever_z=True,
                                 alfa_textura=alfa, sem_sombras=True)

            # Prova independente do corpo/Phong: mesmo loader, sampler e
            # recurso de textura, mas um triângulo sem overdraw. Mantém
            # blending OFF e A2C OFF em 1× e 4×.
            from auditar_alpha_textura_gpu import verificar_textura_na_gpu
            auditoria_rgba = verificar_textura_na_gpu(
                cena, {alfa: caminho for alfa, (caminho, _meta)
                       in texturas_varredura.items()}
            )

            documento = json.loads(provisorio.read_text(encoding="utf-8"))
            documento.update({
                "backend": "Vulkan",
                "dimensoes_imagem": [1024, 768],
                "tipo_experimento": "A2C_MSAA_RGB_SEM_HOMOLOGACAO",
                "api_captura": "CenaVulkan.capturar_framebuffer (RGB, nao renderAlphaMask)",
                "camera": parametros_camera,
                "textura_controle": textura_meta,
                "texturas_varredura": {
                    str(alfa): meta for alfa, (_path, meta) in
                    sorted(texturas_varredura.items())
                },
                "auditoria_rgba_gpu_sem_overdraw": auditoria_rgba,
                "amostras_iniciais": amostras_originais,
                "suporte_msaa": suporte,
                "controles": registros,
                "a2c_altera_blend_pipeline": True,
                "nota": (
                    "Controles extras isolam blend, escrita Z e A2C; "
                    "variantes temporárias da cena são restauradas."
                ),
                "comparacao": {},
            })
            if suporte["disponivel"]:
                validar_controles({nome: registros[nome] for nome in CONTROLES})
                documento["comparacao"] = {
                    "msaa_1x_vs_4x": comparar_rgb(
                        imagens["1x_sem_a2c"], imagens["4x_sem_a2c"]
                    ),
                    "a2c_4x_off_vs_on": comparar_rgb(
                        imagens["4x_sem_a2c"], imagens["4x_com_a2c"]
                    ),
                    "a2c_4x_on_vs_inelegivel": comparar_rgb(
                        imagens["4x_com_a2c"], imagens["4x_inelegivel"]
                    ),
                    "somente_blend_4x": comparar_rgb(
                        imagens["4x_sem_a2c"],
                        imagens["4x_sem_a2c_sem_blend_sem_z"]
                    ),
                    "somente_depth_write_4x": comparar_rgb(
                        imagens["4x_sem_a2c_sem_blend_sem_z"],
                        imagens["4x_sem_a2c_sem_blend_com_z"]
                    ),
                    "somente_a2c_4x": comparar_rgb(
                        imagens["4x_sem_a2c_sem_blend_com_z"],
                        imagens["4x_com_a2c"]
                    ),
                    "somente_a2c_4x_alfa64": comparar_rgb(
                        imagens["4x_a064_sem_a2c_sem_blend_com_z"],
                        imagens["4x_a064_com_a2c"]
                    ),
                    "somente_a2c_4x_alfa192": comparar_rgb(
                        imagens["4x_a192_sem_a2c_sem_blend_com_z"],
                        imagens["4x_a192_com_a2c"]
                    ),
                    "repeticao_a128_off": comparar_rgb(
                        imagens["4x_sem_a2c_sem_blend_com_z"],
                        imagens["4x_a128_repeticao_sem_a2c_sem_blend_com_z"]
                    ),
                    "alfa64_vs128_off": comparar_rgb(
                        imagens["4x_a064_sem_a2c_sem_blend_com_z"],
                        imagens["4x_sem_a2c_sem_blend_com_z"]
                    ),
                    "alfa192_vs128_off": comparar_rgb(
                        imagens["4x_a192_sem_a2c_sem_blend_com_z"],
                        imagens["4x_sem_a2c_sem_blend_com_z"]
                    ),
                    "alfa64_vs128_on": comparar_rgb(
                        imagens["4x_a064_com_a2c"],
                        imagens["4x_com_a2c"]
                    ),
                    "alfa192_vs128_on": comparar_rgb(
                        imagens["4x_a192_com_a2c"],
                        imagens["4x_com_a2c"]
                    ),
                    "alfa64_vs128_off_sem_sombras": comparar_rgb(
                        imagens["4x_a064_sem_a2c_sem_blend_com_z_sem_sombras"],
                        imagens["4x_a128_sem_a2c_sem_blend_com_z_sem_sombras"]
                    ),
                    "alfa192_vs128_off_sem_sombras": comparar_rgb(
                        imagens["4x_a192_sem_a2c_sem_blend_com_z_sem_sombras"],
                        imagens["4x_a128_sem_a2c_sem_blend_com_z_sem_sombras"]
                    ),
                    "alfa128_sombras_on_vs_off": comparar_rgb(
                        imagens["4x_sem_a2c_sem_blend_com_z"],
                        imagens["4x_a128_sem_a2c_sem_blend_com_z_sem_sombras"]
                    ),
                }
                mudou = documento["comparacao"]["a2c_4x_off_vs_on"]["pixels_divergentes"] > 0
                documento["resultado_a2c"] = (
                    "EXECUTADO_DIFERENCA_RGB" if mudou else "EXECUTADO_SEM_DIFERENCA_RGB"
                )
            else:
                documento["resultado_a2c"] = "NAO_TESTAVEL_MSAA_4X"
            destino.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            print("A2C_VULKAN: " + documento["resultado_a2c"], flush=True)
        except BaseException as exc:
            traceback.print_exc()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps({
                "estado": "ERRO", "backend": "Vulkan",
                "tipo_experimento": "A2C_MSAA_RGB_SEM_HOMOLOGACAO",
                "erro": f"{type(exc).__name__}: {exc}",
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            if cena is not None and amostras_originais is not None:
                cena.configurar_multisampling(amostras_originais > 1)
            if material is not None and originais:
                material.shader = originais["shader"]
                material.diffuseTexture = originais["textura"]
                material.configureShading(diffuse=originais["diffuse"])
                material.opacity = originais["opacity"]
                material.transparent = originais["transparent"]
                material.alphaToCoverage = originais["a2c"]
                material.receiveShadows = originais["recebe_sombras"]

    QtCore.QTimer.singleShot(250, medir)


def unload(app):
    pass
