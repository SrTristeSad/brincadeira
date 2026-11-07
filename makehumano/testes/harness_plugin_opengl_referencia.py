"""Plugin descartável para capturar MakeHuman upstream OpenGL fixado.

Executado somente em checkout de referência a8bc2d54, fora do produto.
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
    png_sem_especular = png.with_name(png.stem + "-specular-off.png")
    png_sem_sombras = png.with_name(png.stem + "-shadows-off.png")
    png_so_difusa = png.with_name(png.stem + "-diffuse-only.png")
    png_mascara = png.with_name(png.stem + "-alpha-api.png")
    png_parcial_rgb = png.with_name(png.stem + "-alpha-parcial-rgb.png")
    png_parcial_mascara = png.with_name(png.stem + "-alpha-parcial-api.png")
    pasta_testes = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if pasta_testes not in sys.path:
        sys.path.insert(0, pasta_testes)
    from registrar_estado_material import descrever_material, descrever_iluminacao
    from configurar_camera_paridade import fixar_camera, manifesto_camera
    from registrar_geometria_paridade import descrever_geometria
    from registrar_mascara_paridade import registrar_mascara
    from textura_alpha_controle import construir_textura_alfa_parcial

    iniciado = False

    def medir():
        nonlocal iniciado
        if iniciado:
            return
        # No upstream, startupSequence fecha a splash ao final. O evento
        # de QTimer só é processado quando startupSequence libera o loop.
        if getattr(app, "splash", None) is not None:
            QtCore.QTimer.singleShot(200, medir)
            return
        iniciado = True
        try:
            import numpy as np
            import mh
            from core import G
            from getpath import getSysDataPath

            cam = fixar_camera(app)
            material = app.selectedHuman.material
            material.shader = getSysDataPath("shaders/glsl/phong")
            material.configureShading(diffuse=True)
            estado = descrever_material(material)
            geometria = descrever_geometria(G.world, material)
            parametros = manifesto_camera(cam)
            try:
                G.canvas.makeCurrent()
            except AttributeError:
                pass
            imagem = mh.renderToBuffer(1024, 768)
            # Consulta real ao estado OpenGL: diagnóstico, não modifica a cena.
            try:
                from OpenGL.GL import (
                    glGetLightfv, glGetString, GL_LIGHT0, GL_POSITION, GL_RENDERER, GL_VERSION,
                )
                pos_luz_eye = np.asarray(
                    glGetLightfv(GL_LIGHT0, GL_POSITION), dtype=np.float64
                ).reshape(-1)
                pos_luz_mundo = np.asarray(app.scene.lights[0].position, dtype=np.float64)
                expected_eye = np.asarray(parametros["view"], dtype=np.float64) @ np.array(
                    [*pos_luz_mundo, 1.0], dtype=np.float64
                )
                estado_gl_luz = {
                    "observado": True,
                    "posicao_luz_eye_gl": pos_luz_eye.tolist(),
                    "posicao_luz_eye_view_esperada": expected_eye.tolist(),
                    "divergencia_eye": (pos_luz_eye - expected_eye).tolist(),
                    "renderer": glGetString(GL_RENDERER).decode("utf-8", "replace"),
                    "versao_gl": glGetString(GL_VERSION).decode("utf-8", "replace"),
                }
            except Exception as exc:
                estado_gl_luz = {"observado": False, "erro": f"{type(exc).__name__}: {exc}"}
            especular_original = tuple(material.specularColor.values)
            try:
                material.specularColor = (0.0, 0.0, 0.0)
                estado_sem_especular = descrever_material(material)
                imagem_sem_especular = mh.renderToBuffer(1024, 768)
            finally:
                material.specularColor = especular_original
            sombras_original = bool(material.receiveShadows)
            try:
                material.receiveShadows = False
                estado_sem_sombras = descrever_material(material)
                imagem_sem_sombras = mh.renderToBuffer(1024, 768)
            finally:
                material.receiveShadows = sombras_original
            ambiente_original = tuple(material.ambientColor.values)
            try:
                material.ambientColor = (0.0, 0.0, 0.0)
                material.specularColor = (0.0, 0.0, 0.0)
                material.receiveShadows = False
                estado_so_difusa = descrever_material(material)
                imagem_so_difusa = mh.renderToBuffer(1024, 768)
            finally:
                material.ambientColor = ambiente_original
                material.specularColor = especular_original
                material.receiveShadows = sombras_original
            # Máscara real do contrato original, NÃO canal alfa inferido do PNG RGB.
            imagem_mascara = mh.renderAlphaMask(1024, 768)

            # Só neste checkout descartável: alpha=128 na textura,
            # opacity=1 e A2C desligado. Isola semântica da textura.
            textura_original = material.diffuseTexture
            opacidade_original = float(material.opacity)
            transparencia_original = bool(material.transparent)
            a2c_original = bool(material.alphaToCoverage)
            config_difusa_original = bool(material.shaderConfig.get("diffuse", False))
            textura_parcial, metadados_textura = construir_textura_alfa_parcial()
            try:
                material.diffuseTexture = textura_parcial
                material.configureShading(diffuse=True)
                material.opacity = 1.0
                material.transparent = True
                material.alphaToCoverage = False
                estado_parcial = descrever_material(material)
                if estado_parcial.get("define_diffuse_ativo") is not True:
                    raise RuntimeError("OpenGL sem DIFFUSE no controle parcial")
                imagem_parcial_rgb = mh.renderToBuffer(1024, 768)
                imagem_parcial_mascara = mh.renderAlphaMask(1024, 768)
            finally:
                material.diffuseTexture = textura_original
                material.configureShading(diffuse=config_difusa_original)
                material.opacity = opacidade_original
                material.transparent = transparencia_original
                material.alphaToCoverage = a2c_original

            pixels = np.asarray(imagem.data)
            pixels_sem_especular = np.asarray(imagem_sem_especular.data)
            pixels_sem_sombras = np.asarray(imagem_sem_sombras.data)
            pixels_so_difusa = np.asarray(imagem_so_difusa.data)
            if pixels_sem_especular.shape != pixels.shape or pixels_sem_especular.dtype != np.uint8:
                raise RuntimeError("Captura OpenGL sem especular inválida")
            if pixels_sem_sombras.shape != pixels.shape or pixels_sem_sombras.dtype != np.uint8:
                raise RuntimeError("Captura OpenGL sem sombras inválida")
            if pixels_so_difusa.shape != pixels.shape or pixels_so_difusa.dtype != np.uint8:
                raise RuntimeError("Captura OpenGL só difusa inválida")
            if pixels.shape != (768, 1024, 3) or pixels.dtype != np.uint8:
                raise RuntimeError(
                    f"Captura OpenGL RGB inesperada: shape={pixels.shape} tipo={pixels.dtype}"
                )
            png.parent.mkdir(parents=True, exist_ok=True)
            imagem.save(str(png))
            imagem_sem_especular.save(str(png_sem_especular))
            imagem_sem_sombras.save(str(png_sem_sombras))
            imagem_so_difusa.save(str(png_so_difusa))
            info_mascara = registrar_mascara(imagem_mascara, png_mascara)
            imagem_parcial_rgb.save(str(png_parcial_rgb))
            info_mascara_parcial = registrar_mascara(
                imagem_parcial_mascara, png_parcial_mascara
            )
            resultado = {
                "estado": "CAPTURADO",
                "origem": "MakeHuman upstream OpenGL isolado",
                "backend": "OpenGL",
                "sha_upstream_esperado": "a8bc2d54ff0ac92e78ff71431b1023eda42bf482",
                "shader": "phong",
                "camera": parametros,
                "material": estado,
                "material_sem_especular": estado_sem_especular,
                "material_sem_sombras": estado_sem_sombras,
                "material_so_difusa": estado_so_difusa,
                "captura_mascara_api": True,
                "mascara_alfa": info_mascara,
                "captura_mascara_parcial_api": True,
                "mascara_alfa_parcial": info_mascara_parcial,
                "controle_alfa_parcial": {
                    "textura": metadados_textura,
                    "material": estado_parcial,
                    "sha256_png_rgb": hashlib.sha256(png_parcial_rgb.read_bytes()).hexdigest(),
                    "arquivo_png_rgb": str(png_parcial_rgb),
                },
                "geometria": geometria,
                "estado_gl_luz": estado_gl_luz,
                "iluminacao": descrever_iluminacao(app.scene),
                "G_windowWidth": int(G.windowWidth),
                "G_windowHeight": int(G.windowHeight),
                "numpy": np.__version__,
                "dimensoes_imagem": [1024, 768],
                "pixel_canto_superior_esquerdo": [int(v) for v in pixels[0, 0]],
                "sha256_rgb": hashlib.sha256(pixels.tobytes()).hexdigest(),
                "sha256_png": hashlib.sha256(png.read_bytes()).hexdigest(),
                "sha256_png_sem_especular": hashlib.sha256(png_sem_especular.read_bytes()).hexdigest(),
                "sha256_png_sem_sombras": hashlib.sha256(png_sem_sombras.read_bytes()).hexdigest(),
                "sha256_png_so_difusa": hashlib.sha256(png_so_difusa.read_bytes()).hexdigest(),
                "arquivo_png": str(png),
                "arquivo_png_sem_especular": str(png_sem_especular),
                "arquivo_png_sem_sombras": str(png_sem_sombras),
                "arquivo_png_so_difusa": str(png_so_difusa),
                "captura_especular_desligado": True,
                "captura_sombras_desligadas": True,
                "captura_so_difusa": True,
                "pareado_com_vulkan": False,
            }
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("MAKEHUMANO_REF_OPENGL: " + json.dumps({
                "estado": resultado["estado"],
                "camera": {
                    "fov": parametros["fov"],
                    "centro": parametros["centro"],
                    "radius": parametros["radius"],
                    "projecao": parametros["projecao"],
                },
                "shaderDefines": estado.get("shaderDefines"),
                "pixel_canto": resultado["pixel_canto_superior_esquerdo"],
            }, ensure_ascii=False), flush=True)
        except BaseException as exc:
            traceback.print_exc()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps({
                    "estado": "ERRO", "erro": f"{type(exc).__name__}: {exc}",
                    "backend": "OpenGL", "pareado_com_vulkan": False,
                }, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    QtCore.QTimer.singleShot(250, medir)


def unload(app):
    pass
