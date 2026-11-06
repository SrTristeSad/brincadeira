"""Matemática da projeção original, testável sem importar a interface Qt."""
import numpy as np


def direcao_camera(mesh, camera):
    """Direção de observação em espaço local, incluindo a rotação orbital."""
    eye = np.asarray([*camera.eye, 1.], dtype=np.float64).reshape(4, 1)
    focus = np.asarray([*camera.focus, 1.], dtype=np.float64).reshape(4, 1)
    transform = np.linalg.inv(np.asarray(camera.getModelMatrix(mesh.object3d)))
    eye = transform @ eye
    focus = transform @ focus
    direction = eye[:3, 0]/eye[3, 0] - focus[:3, 0]/focus[3, 0]
    return direction/np.sqrt(np.sum(direction**2))
