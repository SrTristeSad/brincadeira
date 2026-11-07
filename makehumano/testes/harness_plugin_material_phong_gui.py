"""Experimento Phong transitório: configura duas capturas na GUI da CI.

NÃO é plug-in do produto: copiado temporariamente pelo runner de testes.
NÃO compara OpenGL; altera somente o estado local do processo descartável.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

from PyQt5 import QtCore
from core import G


def _sha_imagem(pixels):
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def load(app):
    destino_str = os.environ.get("MAKEHUMANO_HARNESS_FORMATO_JSON")
    if not destino_str:
        raise RuntimeError("Harness Phong exige destino JSON")
    pasta_testes = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if pasta_testes not in sys.path:
        sys.path.insert(0, pasta_testes)
    from observar_formato_cena_vulkan import observar_captura_offscreen
    from registrar_estado_material import descrever_material, descrever_iluminacao

    destino = Path(destino_str)
    png_on = Path(os.environ["MAKEHUMANO_HARNESS_FORMATO_PNG"])
    png_off = png_on.with_name(png_on.stem + "-diffuse-off.png")
    png_sint_on = png_on.with_name(png_on.stem + "-sintetico-on.png")
    png_sint_off = png_on.with_name(png_on.stem + "-sintetico-off.png")
    observacao = destino.with_name(destino.stem + "-observacao.json")
    iniciado = False

    def medir():
        nonlocal iniciado
        if iniciado:
            return
        if not getattr(app, "_startup_complete", False):
            QtCore.QTimer.singleShot(200, medir)
            return
        iniciado = True
        material = None
        shader_original = None
        diffuse_original = None
        textura_original = None
        try:
            import mh
            import numpy as np
            from getpath import getSysDataPath

            canvas = G.canvas
            cena = canvas._garantir_cena()
            material = app.selectedHuman.material
            shader_original = material.shader
            diffuse_original = bool(material.shaderConfig.get("diffuse", False))
            textura_original = material.diffuseTexture
            objetos_corpo = [
                obj for obj in G.world
                if getattr(obj, "material", None) is material
                and getattr(obj, "visibility", True)
                and getattr(obj, "solid", True)
            ]
            if not objetos_corpo:
                raise RuntimeError("Material do corpo não encontrado entre objetos G.world")
            corpo = max(objetos_corpo, key=lambda obj: len(obj.primitives))
            camera = G.cameras[corpo.cameraMode]
            proj_antes, view_antes = camera.getMatrices(0)

            # Apenas no processo efêmero de CI: alternar o mesmo preset
            # e a opção preexistente de textura difusa, não criar feature.
            material.shader = getSysDataPath("shaders/glsl/phong")
            material.configureShading(diffuse=True)
            estado_on = descrever_material(material)
            is_textured_on = bool(corpo.isTextured)
            if not is_textured_on:
                raise RuntimeError("isTextured não refletiu shaderConfig diffuse=True")

            with observar_captura_offscreen(cena, observacao):
                img_on = mh.renderToBuffer(1024, 768)
                material.configureShading(diffuse=False)
                estado_off = descrever_material(material)
                is_textured_off = bool(corpo.isTextured)
                if is_textured_off:
                    raise RuntimeError("isTextured não refletiu shaderConfig diffuse=False")
                img_off = mh.renderToBuffer(1024, 768)

                # Controle POSITIVO isolado: textura sintética, descartada
                # junto com este processo CI. Não modifica assets de produção.
                from image import Image
                desenho = np.empty((16, 16, 4), dtype=np.uint8)
                desenho[:, :, :] = (235, 45, 35, 255)
                yy, xx = np.indices((16, 16))
                desenho[((xx // 4 + yy // 4) % 2) == 0] = (20, 185, 245, 255)
                checksum_textura = hashlib.sha256(desenho.tobytes()).hexdigest()
                material.diffuseTexture = Image(data=desenho)
                material.configureShading(diffuse=True)
                estado_sint_on = descrever_material(material)
                obj_textura_sint = getattr(corpo, "texture", None)
                obj_textura_tipo = (
                    type(obj_textura_sint).__name__
                    if obj_textura_sint is not None else None
                )
                img_sint_on = mh.renderToBuffer(1024, 768)
                material.configureShading(diffuse=False)
                estado_sint_off = descrever_material(material)
                img_sint_off = mh.renderToBuffer(1024, 768)

            dados_on, dados_off = np.asarray(img_on.data), np.asarray(img_off.data)
            if dados_on.shape != (768, 1024, 3) or dados_off.shape != dados_on.shape:
                raise RuntimeError(f"RGB inesperado: on={dados_on.shape}, off={dados_off.shape}")
            if dados_on.dtype != np.uint8 or dados_off.dtype != np.uint8:
                raise RuntimeError("Os PNGs precisam preservar bytes RGB uint8")
            dados_sint_on = np.asarray(img_sint_on.data)
            dados_sint_off = np.asarray(img_sint_off.data)
            if dados_sint_on.shape != dados_on.shape or dados_sint_off.shape != dados_on.shape:
                raise RuntimeError("Controle sintético não gerou a mesma resolução RGB")
            delta = np.abs(dados_on.astype(np.int16) - dados_off.astype(np.int16))
            delta_sint = np.abs(
                dados_sint_on.astype(np.int16) - dados_sint_off.astype(np.int16)
            )
            pixels_sint = np.any(delta_sint > 8, axis=2)
            pixels = np.any(delta > 8, axis=2)
            proj_depois, view_depois = camera.getMatrices(0)
            camera_igual = bool(
                np.array_equal(np.asarray(proj_antes), np.asarray(proj_depois))
                and np.array_equal(np.asarray(view_antes), np.asarray(view_depois))
            )
            png_on.parent.mkdir(parents=True, exist_ok=True)
            img_on.save(str(png_on))
            img_off.save(str(png_off))
            img_sint_on.save(str(png_sint_on))
            img_sint_off.save(str(png_sint_off))
            evidencia = json.loads(observacao.read_text(encoding="utf-8"))
            evidencia.update({
                "origem": "GUI Vulkan efemera CI: phong diffuse on/off",
                "pareado_com_opengl": False,
                "shader_efetivo": str(material.shader),
                "shader_esperado": "phong",
                "numpy": np.__version__,
                "cenario": "Mesmo processo, cena e camera; shader Phong; alternancia diffuse",
                "camara_matrizes_iguais": camera_igual,
                "estado_material_phong_on": estado_on,
                "estado_material_phong_off": estado_off,
                "estado_material_sintetico_on": estado_sint_on,
                "estado_material_sintetico_off": estado_sint_off,
                "objeto_textura_sintetica_tipo": obj_textura_tipo,
                "sha256_textura_sintetica_rgba": checksum_textura,
                "textura_ativa_no_objeto_on": is_textured_on,
                "textura_ativa_no_objeto_off": is_textured_off,
                "iluminacao": descrever_iluminacao(app.scene),
                "dimensoes_imagem": [1024, 768],
                "pixel_fundo_on": [int(v) for v in dados_on[0, 0]],
                "pixel_fundo_off": [int(v) for v in dados_off[0, 0]],
                "comparacao_sintetica_on_off": {
                    "total_pixels": int(pixels_sint.size),
                    "pixels_divergentes_tolerancia_8": int(np.count_nonzero(pixels_sint)),
                    "fracao_divergente_tolerancia_8": float(np.mean(pixels_sint)),
                    "erro_medio_rgb": float(np.mean(delta_sint)),
                    "erro_maximo_rgb": int(delta_sint.max()),
                    "comparacao_interna_apenas": True,
                    "nota": "Teste positivo com Image RGBA gerado em memória.",
                },
                "comparacao_on_off": {
                    "total_pixels": int(pixels.size),
                    "pixels_divergentes_tolerancia_8": int(np.count_nonzero(pixels)),
                    "fracao_divergente_tolerancia_8": float(np.mean(pixels)),
                    "erro_medio_rgb": float(np.mean(delta)),
                    "erro_maximo_rgb": int(delta.max()),
                    "comparacao_interna_apenas": True,
                },
                "sha256_rgb_on": _sha_imagem(dados_on),
                "sha256_rgb_off": _sha_imagem(dados_off),
                "arquivos_png": [
                    str(png_on), str(png_off),
                    str(png_sint_on), str(png_sint_off),
                ],
                "sha256_png_on": hashlib.sha256(png_on.read_bytes()).hexdigest(),
                "sha256_png_off": hashlib.sha256(png_off.read_bytes()).hexdigest(),
                "sha256_png_sint_on": hashlib.sha256(png_sint_on.read_bytes()).hexdigest(),
                "sha256_png_sint_off": hashlib.sha256(png_sint_off.read_bytes()).hexdigest(),
                "teste_de_material_concluido": True,
            })
            if not camera_igual:
                raise RuntimeError("Matrizes da camera mudaram durante o teste controlado")
            if evidencia["estado"] != "OBSERVADO":
                raise RuntimeError("Captura real 1024x768 não observada")
            if len(evidencia["texturas_offscreen_observadas"]) != 4:
                raise RuntimeError("Esperados quatro alvos 1024x768")
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(evidencia, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("MAKEHUMANO_HARNESS_PHONG: " + json.dumps({
                "estado": evidencia["estado"],
                "formato": evidencia["formato_cena_inicial"],
                "camara_igual": camera_igual,
                "diffuse_on": is_textured_on,
                "diffuse_off": is_textured_off,
                "fracao_divergente_on_off": evidencia["comparacao_on_off"]["fracao_divergente_tolerancia_8"],
                "fracao_divergente_sintetica": evidencia["comparacao_sintetica_on_off"]["fracao_divergente_tolerancia_8"],
                "objeto_textura_sintetica_tipo": obj_textura_tipo,
                "pixel_fundo_on": evidencia["pixel_fundo_on"],
                "pixel_fundo_off": evidencia["pixel_fundo_off"],
            }, ensure_ascii=False), flush=True)
        except BaseException as exc:
            traceback.print_exc()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps({
                "estado": "ERRO",
                "erro": f"{type(exc).__name__}: {exc}",
                "pareado_com_opengl": False,
                "teste_de_material_concluido": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            # O processo inteiro é isolado; restaurar o estado mesmo assim.
            if material is not None and shader_original is not None:
                try:
                    material.diffuseTexture = textura_original
                    material.shader = shader_original
                    material.configureShading(diffuse=diffuse_original)
                except Exception:
                    traceback.print_exc()

    QtCore.QTimer.singleShot(200, medir)


def unload(app):
    pass
