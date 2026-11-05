"""Seleção das FaceGroups da interface MakeHuman original sem OpenGL."""

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "codigo" / "makehuman" / "lib"))

from vulkan_picking import selecionar_cor


def camera():
    ident = np.eye(4, dtype=np.float32)
    return SimpleNamespace(
        updated=True, getMatrices=lambda _eye: (ident, ident),
        getModelMatrix=lambda obj: ident,
    )


def objeto(nome, z=0.4, *, pickable=True, visivel=True, prioridade=0,
           indices=None, grupos=None, cores=None, cull=0):
    vertices = np.array([
        [-0.8, -0.8, z], [0.8, -0.8, z],
        [0.8, 0.8, z], [-0.8, 0.8, z],
    ], dtype=np.float32)
    return SimpleNamespace(
        name=nome, verts=vertices,
        primitives=np.asarray(
            indices if indices is not None else [[0, 1, 2], [0, 2, 3]],
            dtype=np.uint32
        ),
        groups=grupos if grupos is not None else [(0, 2)],
        clrid=lambda i: (
            cores[i] if cores is not None else (255, 0, 0)
        ),
        visibility=visivel, pickable=pickable, cameraMode=0,
        priority=prioridade, cull=cull,
    )


class TestarPickingOriginal(unittest.TestCase):
    def test_facegroup_usa_cor_id_original_e_quadrante(self):
        obj = objeto(
            "corpo", grupos=[(0, 1), (1, 1)],
            cores=[(17, 24, 33), (43, 52, 61)],
        )
        cameras = [camera()]
        self.assertEqual(
            selecionar_cor([obj], cameras, 70, 35, 100, 100),
            (17, 24, 33),
        )
        self.assertEqual(
            selecionar_cor([obj], cameras, 30, 65, 100, 100),
            (43, 52, 61),
        )

    def test_depth_e_visibilidade_seguem_a_cena_original(self):
        frente = objeto("perto", z=0.15, cores=[(1, 2, 3)], prioridade=0)
        atras = objeto("longe", z=0.65, cores=[(4, 5, 6)], prioridade=10)
        self.assertEqual(
            selecionar_cor([frente, atras], [camera()], 50, 50, 100, 100),
            (1, 2, 3),
        )
        frente.visibility = False
        self.assertEqual(
            selecionar_cor([frente, atras], [camera()], 50, 50, 100, 100),
            (4, 5, 6),
        )
        frente.visibility = True
        frente.pickable = False
        self.assertEqual(
            selecionar_cor([frente, atras], [camera()], 50, 50, 100, 100),
            (4, 5, 6),
        )

    def test_quad_degenerado_e_cull(self):
        original = objeto(
            "tri", indices=[[0, 1, 2, 0]],
            cores=[(8, 16, 32)],
            grupos=[(0, 1)],
        )
        self.assertEqual(
            selecionar_cor([original], [camera()], 70, 70, 100, 100),
            (8, 16, 32),
        )
        original.cull = -1  # remove frente NDC CCW
        self.assertEqual(
            selecionar_cor([original], [camera()], 70, 70, 100, 100),
            (0, 0, 0),
        )

    def test_fora_da_viewport_e_malhas_inadequadas(self):
        obj = objeto("corpo")
        for x, y in ((-1, 4), (100, 2), (2, -3), (2, 120),
                     (None, 1), (1, None)):
            self.assertEqual(
                selecionar_cor([obj], [camera()], x, y, 100, 100),
                (0, 0, 0),
            )
        obj.primitives = np.empty((0, 4), dtype=np.uint32)
        self.assertEqual(
            selecionar_cor([obj], [camera()], 50, 50, 100, 100),
            (0, 0, 0),
        )

    def test_usa_matriz_original_apos_mudanca_de_camera(self):
        original = objeto("objeto")
        cam = camera()
        m = np.eye(4, dtype=np.float32)
        m[0, 3] = 1.5
        cam.getModelMatrix = lambda obj: m
        self.assertEqual(
            selecionar_cor([original], [cam], 50, 50, 100, 100),
            (0, 0, 0),
        )
        cam.getModelMatrix = lambda obj: np.eye(4, dtype=np.float32)
        self.assertEqual(
            selecionar_cor([original], [cam], 50, 50, 100, 100),
            (255, 0, 0),
        )


if __name__ == "__main__":
    unittest.main()
