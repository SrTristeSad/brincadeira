"""Parâmetros comuns de câmera dos harnesses OpenGL e Vulkan externos.

Apenas para diagnóstico, NÃO instalado no produto. A projeção original é
preservada e registrada (não presumimos que seja perspectiva).
"""
import numpy as np


CENTRO = (0.0, 0.11924934387207031, 0.0)
RAIO = 12.251182769327169
FOV = 90.0


def fixar_camera(app):
    cam = app.modelCamera
    cam.noAutoScale = True
    cam.center = list(CENTRO)
    cam.radius = RAIO
    cam.fovAngle = FOV
    cam.zoomFactor = 1.0
    cam.translation = [0.0, 0.0, 0.0]
    cam.horizontalRotation = 0.0
    cam.verticalInclination = 0.0
    cam.changed()
    return cam


def manifesto_camera(cam):
    proj, view = cam.getMatrices(0)
    return {
        "classe": type(cam).__name__,
        "fov": float(cam.fovAngle),
        "centro": [float(v) for v in cam.center],
        "radius": float(cam.radius),
        "projecao": int(cam.projection),
        "near": float(cam.nearPlane),
        "far": float(cam.farPlane),
        "zoom": float(cam.zoomFactor),
        "rotacao_horizontal": float(cam.horizontalRotation),
        "inclinacao_vertical": float(cam.verticalInclination),
        "translation": [float(v) for v in cam.translation],
        "view": np.asarray(view, dtype=float).tolist(),
        "proj": np.asarray(proj, dtype=float).tolist(),
    }
