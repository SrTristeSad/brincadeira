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

            def captar(nome, *, amostras, transparente, a2c):
                material.transparent = transparente
                material.alphaToCoverage = a2c
                glmodule.have_multisample = amostras == 4
                expected = bool(
                    glmodule.have_multisample
                    and int(corpo.nTransparentPrimitives) > 0
                    and bool(corpo.alphaToCoverage)
                )
                tracos = {"fbo": [], "ativacoes_a2c": 0, "desativacoes_a2c": 0}
                original_draw = glmodule.draw
                original_enable = glmodule.glEnable
                original_disable = glmodule.glDisable

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
                    if int(cap) == int(GL.GL_SAMPLE_ALPHA_TO_COVERAGE):
                        tracos["ativacoes_a2c"] += 1
                    return original_enable(cap)

                def observar_disable(cap):
                    if int(cap) == int(GL.GL_SAMPLE_ALPHA_TO_COVERAGE):
                        tracos["desativacoes_a2c"] += 1
                    return original_disable(cap)

                glmodule.draw = observar_draw
                glmodule.glEnable = observar_enable
                glmodule.glDisable = observar_disable
                try:
                    imagem = mh.renderToBuffer(1024, 768)
                finally:
                    glmodule.draw = original_draw
                    glmodule.glEnable = original_enable
                    glmodule.glDisable = original_disable

                rgb = np.ascontiguousarray(np.asarray(imagem.data))
                if not tracos["fbo"] or not tracos["fbo"][0]["completo"]:
                    raise RuntimeError("FBO OpenGL ausente ou incompleto")
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
                    "amostras": amostras_fbo,
                    "a2c_flag_material": bool(a2c),
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

            comparacoes = {}
            if suporte["testavel"]:
                for nome, a, b in (
                    ("msaa_1x_vs_4x", "1x_sem_a2c", "4x_sem_a2c"),
                    ("a2c_4x_off_vs_on", "4x_sem_a2c", "4x_com_a2c"),
                    ("a2c_4x_on_vs_inelegivel", "4x_com_a2c", "4x_inelegivel"),
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
                    "API RGB renderToBuffer: OpenGL mistura A2C e blend desativado. "
                    "Não usar renderAlphaMask para inferir A2C."
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
