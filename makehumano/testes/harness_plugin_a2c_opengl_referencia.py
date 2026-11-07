"""A2C RGB no OpenGL upstream pinado, somente em checkout temporário de CI.

Sem alterar Qt, glmodule, mesh, shader, código original ou recursos de produção.
Usa renderToBuffer (FBO); NÃO usa renderAlphaMask, que desliga multisampling.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def load(app):
    from PyQt5 import QtCore
    destino = Path(os.environ["MAKEHUMANO_REF_JSON"])
    png = Path(os.environ["MAKEHUMANO_REF_PNG"])
    pasta = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    from configurar_camera_paridade import fixar_camera, manifesto_camera
    from diagnosticar_a2c_msaa import comparar_rgb, metadados_rgb
    from textura_alpha_controle import salvar_textura_alfa_parcial
    iniciado = False

    def medir():
        nonlocal iniciado
        if iniciado:
            return
        if getattr(app, "splash", None) is not None:
            QtCore.QTimer.singleShot(200, medir)
            return
        iniciado = True
        material = None
        originais = {}
        glmodule = None
        msaa_original = None
        try:
            import numpy as np
            from OpenGL import GL
            import glmodule
            import mh
            from core import G
            from getpath import getSysDataPath

            G.canvas.makeCurrent()
            camera = fixar_camera(app)
            material = app.selectedHuman.material
            originais = {
                "shader": material.shader,
                "textura": material.diffuseTexture,
                "diffuse": bool(material.shaderConfig.get("diffuse", False)),
                "opacity": float(material.opacity),
                "transparent": bool(material.transparent),
                "a2c": bool(material.alphaToCoverage),
            }
            msaa_original = glmodule.have_multisample
            suporte = {
                "cli_multisampling": bool((G.args or {}).get("multisampling", False)),
                "extensao_disponivel": bool(msaa_original),
                "amostras_requeridas": 4,
                "testavel": False,
                "contexto_qt_amostras": int(np.asarray(GL.glGetIntegerv(GL.GL_SAMPLES)).ravel()[0]),
                "renderer": GL.glGetString(GL.GL_RENDERER).decode("utf-8", "replace"),
                "versao_gl": GL.glGetString(GL.GL_VERSION).decode("utf-8", "replace"),
            }
            if not suporte["cli_multisampling"]:
                raise RuntimeError("Runner de A2C OpenGL não recebeu --multisampling")

            corpos = [
                obj for obj in G.world
                if getattr(obj, "material", None) is material
                and getattr(obj, "visibility", True)
                and getattr(obj, "solid", True)
            ]
            if not corpos:
                raise RuntimeError("Corpo OpenGL original ausente")
            corpo = max(corpos, key=lambda obj: len(obj.primitives))
            if corpo.nTransparentPrimitives != 0:
                raise RuntimeError("Controle requer corpo inicial sem transparentes")
            texture_path, textura_meta = salvar_textura_alfa_parcial(
                destino.with_name(destino.stem + "-a2c-textura.png"), alfa=128
            )
            material.shader = getSysDataPath("shaders/glsl/phong")
            material.diffuseTexture = texture_path
            material.configureShading(diffuse=True)
            material.transparent = True
            material.opacity = 1.0
            material.alphaToCoverage = False
            if not corpo.isTextured:
                raise RuntimeError("Textura DIFFUSE não ficou ativa no corpo OpenGL")
            registros = {}
            imagens = {}

            def captar(nome, *, amostras, transparente, a2c,
                       sem_blend=False, escrever_z=False):
                material.transparent = transparente
                material.alphaToCoverage = a2c
                glmodule.have_multisample = amostras == 4
                expected = bool(
                    glmodule.have_multisample
                    and int(corpo.nTransparentPrimitives) > 0
                    and bool(corpo.alphaToCoverage)
                )
                tracos = {
                    "fbo": [], "ativacoes_a2c": 0, "desativacoes_a2c": 0,
                    "corpo_desenhado": 0, "outros_objetos": 0,
                    "draw_states": [], "depth_mask_forcado": 0,
                }
                original_draw = glmodule.draw
                original_draw_mesh = glmodule.drawMesh
                original_enable = glmodule.glEnable
                original_disable = glmodule.glDisable
                original_depthmask = glmodule.glDepthMask
                original_elements = glmodule.glDrawElements
                corpo_em_desenho = False

                def observar_malha(obj, *args, **kwargs):
                    nonlocal corpo_em_desenho
                    if obj is not corpo:
                        tracos["outros_objetos"] += 1
                    else:
                        tracos["corpo_desenhado"] += 1
                    anterior = corpo_em_desenho
                    corpo_em_desenho = obj is corpo
                    blend_antes = bool(GL.glIsEnabled(GL.GL_BLEND))
                    try:
                        if corpo_em_desenho and sem_blend:
                            original_disable(GL.GL_BLEND)
                        return original_draw_mesh(obj, *args, **kwargs)
                    finally:
                        if corpo_em_desenho and sem_blend:
                            (original_enable if blend_antes else original_disable)(GL.GL_BLEND)
                        corpo_em_desenho = anterior

                def observar_draw(*args, **kwargs):
                    tracos["fbo"].append({
                        "id": int(np.asarray(GL.glGetIntegerv(
                            GL.GL_FRAMEBUFFER_BINDING
                        )).ravel()[0]),
                        "amostras": int(np.asarray(GL.glGetIntegerv(
                            GL.GL_SAMPLES
                        )).ravel()[0]),
                        "buffers_multiamostra": int(np.asarray(GL.glGetIntegerv(
                            GL.GL_SAMPLE_BUFFERS
                        )).ravel()[0]),
                        "completo": int(GL.glCheckFramebufferStatus(
                            GL.GL_FRAMEBUFFER
                        )) == int(GL.GL_FRAMEBUFFER_COMPLETE),
                    })
                    resultado = original_draw(*args, **kwargs)
                    if resultado is not True:
                        raise RuntimeError("glmodule.draw não concluiu o FBO RGB")
                    return resultado

                def observar_enable(cap):
                    if corpo_em_desenho and int(cap) == int(GL.GL_SAMPLE_ALPHA_TO_COVERAGE):
                        tracos["ativacoes_a2c"] += 1
                    return original_enable(cap)

                def observar_disable(cap):
                    if corpo_em_desenho and int(cap) == int(GL.GL_SAMPLE_ALPHA_TO_COVERAGE):
                        tracos["desativacoes_a2c"] += 1
                    return original_disable(cap)

                def observar_depthmask(habilitado):
                    if corpo_em_desenho and escrever_z and not bool(habilitado):
                        tracos["depth_mask_forcado"] += 1
                        return original_depthmask(GL.GL_TRUE)
                    return original_depthmask(habilitado)

                def observar_elementos(*args, **kwargs):
                    if corpo_em_desenho:
                        tracos["draw_states"].append({
                            "blend": bool(GL.glIsEnabled(GL.GL_BLEND)),
                            "escrita_z": bool(np.asarray(GL.glGetBooleanv(
                                GL.GL_DEPTH_WRITEMASK
                            )).ravel()[0]),
                            "a2c": bool(GL.glIsEnabled(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)),
                        })
                    return original_elements(*args, **kwargs)

                # O Vulkan renderiza [corpo]; fazer o mesmo neste ensaio GL.
                # Nenhum outro objeto da GUI deve contaminar o traço A2C.
                mundo_original = G.world
                G.world = [corpo]
                glmodule.draw = observar_draw
                glmodule.drawMesh = observar_malha
                glmodule.glEnable = observar_enable
                glmodule.glDisable = observar_disable
                glmodule.glDepthMask = observar_depthmask
                glmodule.glDrawElements = observar_elementos
                try:
                    imagem = mh.renderToBuffer(1024, 768)
                finally:
                    G.world = mundo_original
                    glmodule.draw = original_draw
                    glmodule.drawMesh = original_draw_mesh
                    glmodule.glEnable = original_enable
                    glmodule.glDisable = original_disable
                    glmodule.glDepthMask = original_depthmask
                    glmodule.glDrawElements = original_elements

                rgb = np.ascontiguousarray(np.asarray(imagem.data))
                if not tracos["fbo"] or not tracos["fbo"][0]["completo"]:
                    raise RuntimeError("FBO OpenGL ausente ou incompleto")
                if tracos["corpo_desenhado"] < 1 or tracos["outros_objetos"]:
                    raise RuntimeError("Captura GL não ficou isolada no corpo")
                if not tracos["draw_states"]:
                    raise RuntimeError("Nenhum glDrawElements observado para o corpo")
                blend_esperado = not (sem_blend or expected)
                depth_esperado = bool(escrever_z or expected or
                                      int(corpo.nTransparentPrimitives) == 0)
                if any(
                    estado != {"blend": blend_esperado,
                               "escrita_z": depth_esperado, "a2c": expected}
                    for estado in tracos["draw_states"]
                ):
                    raise RuntimeError(
                        "Estados efetivos GL de blend/profundidade/A2C divergentes: "
                        + json.dumps(tracos["draw_states"], ensure_ascii=False)
                    )
                if escrever_z and tracos["depth_mask_forcado"] == 0:
                    raise RuntimeError("Controle GL não forçou escrita Z")
                observado = bool(tracos["ativacoes_a2c"])
                if observado != expected:
                    raise RuntimeError(
                        "A2C OpenGL diferente do caminho esperado: "
                        + json.dumps({"esperado": expected, "tracos": tracos})
                    )
                if tracos["desativacoes_a2c"] != tracos["ativacoes_a2c"]:
                    raise RuntimeError("A2C GL não foi restaurado")
                saida = png if nome == "1x_sem_a2c" else png.with_name(
                    png.stem + "-" + nome + ".png"
                )
                imagem.save(str(saida))
                amostras_fbo = tracos["fbo"][0]["amostras"]
                registros[nome] = {
                    **metadados_rgb(rgb),
                    "captura_rgb": True,
                    "amostras_solicitadas": amostras,
                    "amostras_fbo_observadas": amostras_fbo,
                    "amostras": max(1, amostras_fbo),  # GL_SAMPLES=0 corresponde a raster 1x
                    "a2c_flag_material": bool(a2c),
                    "controle_blend_desligado": bool(sem_blend),
                    "controle_escrita_z_forcada": bool(escrever_z),
                    "blend_habilitado_observado": bool(blend_esperado),
                    "escrita_z_observada": bool(depth_esperado),
                    "material_transparent": bool(transparente),
                    "opacity": float(material.opacity),
                    "nTransparentPrimitives": int(corpo.nTransparentPrimitives),
                    "a2c_elegivel": expected,
                    "pipeline_a2c_observado": observado,
                    "rastros_gl": tracos,
                    "arquivo_rgb": str(saida),
                    "sha256_png": hashlib.sha256(saida.read_bytes()).hexdigest(),
                }
                imagens[nome] = rgb
                return amostras_fbo

            amostras_1x = captar(
                "1x_sem_a2c", amostras=1, transparente=True, a2c=False
            )
            if amostras_1x != 0:
                raise RuntimeError("FBO 1x reportou GL_SAMPLES diferente de zero")
            if suporte["extensao_disponivel"]:
                try:
                    observadas = captar(
                        "4x_sem_a2c", amostras=4, transparente=True, a2c=False
                    )
                    suporte["amostras_fbo_observadas"] = observadas
                    suporte["testavel"] = observadas == 4
                except Exception as exc:
                    suporte["erro_fbo_4x"] = f"{type(exc).__name__}: {exc}"
                if suporte["testavel"]:
                    captar("4x_com_a2c", amostras=4, transparente=True, a2c=True)
                    captar("4x_inelegivel", amostras=4, transparente=False, a2c=True)
                    # Controles intermediários, totalmente temporários:
                    # mantém MSAA=4 e A2C=OFF; isola BLEND e escrita em Z.
                    captar("4x_sem_a2c_sem_blend_sem_z",
                           amostras=4, transparente=True, a2c=False,
                           sem_blend=True)
                    captar("4x_sem_a2c_sem_blend_com_z",
                           amostras=4, transparente=True, a2c=False,
                           sem_blend=True, escrever_z=True)

            comparacoes = {}
            if suporte["testavel"]:
                for nome, a, b in (
                    ("msaa_1x_vs_4x", "1x_sem_a2c", "4x_sem_a2c"),
                    ("a2c_4x_off_vs_on", "4x_sem_a2c", "4x_com_a2c"),
                    ("a2c_4x_on_vs_inelegivel", "4x_com_a2c", "4x_inelegivel"),
                    ("somente_blend_4x", "4x_sem_a2c",
                     "4x_sem_a2c_sem_blend_sem_z"),
                    ("somente_depth_write_4x", "4x_sem_a2c_sem_blend_sem_z",
                     "4x_sem_a2c_sem_blend_com_z"),
                    ("somente_a2c_4x", "4x_sem_a2c_sem_blend_com_z",
                     "4x_com_a2c"),
                ):
                    comparacoes[nome] = comparar_rgb(imagens[a], imagens[b])
            saida = {
                "estado": "CAPTURADO",
                "tipo_experimento": "A2C_MSAA_RGB_REFERENCIA_GL_SEM_HOMOLOGACAO",
                "backend": "OpenGL",
                "sha_upstream_esperado": "a8bc2d54ff0ac92e78ff71431b1023eda42bf482",
                "camera": manifesto_camera(camera),
                "textura_controle": textura_meta,
                "dimensoes_imagem": [1024, 768],
                "suporte_msaa": suporte,
                "controles": registros,
                "comparacao": comparacoes,
                "resultado_a2c": (
                    "EXECUTADO_COM_MSAA_4X" if suporte["testavel"]
                    else "NAO_TESTAVEL_MSAA_4X"
                ),
                "nota": (
                    "Capturas extras isolam uma mudança por vez: blending, "
                    "escrita Z e cobertura A2C. Instrumentação só na GUI de teste; "
                    "não usar renderAlphaMask."
                ),
            }
            destino.write_text(
                json.dumps(saida, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("A2C_REF_OPENGL: " + saida["resultado_a2c"], flush=True)
        except BaseException as exc:
            traceback.print_exc()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps({
                "estado": "ERRO", "backend": "OpenGL",
                "tipo_experimento": "A2C_MSAA_RGB_REFERENCIA_GL_SEM_HOMOLOGACAO",
                "erro": f"{type(exc).__name__}: {exc}",
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            if glmodule is not None and msaa_original is not None:
                glmodule.have_multisample = msaa_original
            if material is not None and originais:
                material.shader = originais["shader"]
                material.diffuseTexture = originais["textura"]
                material.configureShading(diffuse=originais["diffuse"])
                material.opacity = originais["opacity"]
                material.transparent = originais["transparent"]
                material.alphaToCoverage = originais["a2c"]

    QtCore.QTimer.singleShot(250, medir)


def unload(app):
    pass
