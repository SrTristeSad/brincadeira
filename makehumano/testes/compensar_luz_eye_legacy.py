"""Contraprova: converter luz eye-space já armazenada pelo OpenGL em mundo.

Somente harness de diagnóstico. NUNCA atualizar o renderizador do produto
com esta transformação sem decisão sobre compatibilidade visual.
"""
import numpy as np


def posicao_mundo_para_luz_eye_legacy(matriz_view, posicao_eye):
    """Encontra P_world cujo view @ P_world reproduz gl_LightSource[0].position."""
    view = np.asarray(matriz_view, dtype=np.float64)
    eye = np.asarray(posicao_eye, dtype=np.float64)
    if (view.shape != (4, 4) or eye.shape != (3,)
            or not np.isfinite(view).all() or not np.isfinite(eye).all()):
        raise ValueError("Matriz view 4x4 e posição eye 3D finitas são obrigatórias")
    try:
        mundo = np.linalg.solve(view, np.array([*eye, 1.0], dtype=np.float64))
    except np.linalg.LinAlgError as exc:
        raise ValueError("Matriz view não inversível") from exc
    if abs(mundo[3]) < 1e-10:
        raise ValueError("Luz eye foi projetada com componente homogênea zero")
    mundo = mundo[:3] / mundo[3]
    reconstruido = view @ np.array([*mundo, 1.0])
    if not np.allclose(reconstruido[:3], eye, atol=1e-8, rtol=0):
        raise RuntimeError("A posição world não reproduziu a luz eye do original")
    return [float(v) for v in mundo]
