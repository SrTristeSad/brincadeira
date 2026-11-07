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
    pasta_testes = os.environ["MAKEHUMANO_HARNESS_TESTES_DIR"]
    if pasta_testes not in sys.path:
        sys.path.insert(0, pasta_testes)
    from registrar_estado_material import descrever_material, descrever_iluminacao
    from configurar_camera_paridade import fixar_camera, manifesto_camera

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
            parametros = manifesto_camera(cam)
            try:
                G.canvas.makeCurrent()
            except AttributeError:
                pass
            imagem = mh.renderToBuffer(1024, 768)
            pixels = np.asarray(imagem.data)
            if pixels.shape != (768, 1024, 3) or pixels.dtype != np.uint8:
                raise RuntimeError(
                    f"Captura OpenGL RGB inesperada: shape={pixels.shape} tipo={pixels.dtype}"
                )
            png.parent.mkdir(parents=True, exist_ok=True)
            imagem.save(str(png))
            resultado = {
                "estado": "CAPTURADO",
                "origem": "MakeHuman upstream OpenGL isolado",
                "backend": "OpenGL",
                "sha_upstream_esperado": "a8bc2d54ff0ac92e78ff71431b1023eda42bf482",
                "shader": "phong",
                "camera": parametros,
                "material": estado,
                "iluminacao": descrever_iluminacao(app.scene),
                "G_windowWidth": int(G.windowWidth),
                "G_windowHeight": int(G.windowHeight),
                "numpy": np.__version__,
                "dimensoes_imagem": [1024, 768],
                "pixel_canto_superior_esquerdo": [int(v) for v in pixels[0, 0]],
                "sha256_rgb": hashlib.sha256(pixels.tobytes()).hexdigest(),
                "sha256_png": hashlib.sha256(png.read_bytes()).hexdigest(),
                "arquivo_png": str(png),
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
