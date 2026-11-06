"""Seleção das FaceGroups da interface MakeHuman original sem OpenGL."""

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "codigo" / "makehuman" / "lib"))

from vulkan_picking import selecionar_cor, selecionar_profundidade


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


    def test_recorte_near_mantem_parte_visivel_e_culling(self):
        """Um vértice atrás da câmera não deve descartar a face inteira."""
        original = objeto(
            "atravessa_near", indices=[[0, 1, 2]],
            grupos=[(0, 1)], cores=[(12, 34, 56)],
        )
        original.verts = np.array([
            [-0.7, -0.7, -1.4], [0.7, -0.7, 0.4],
            [0.0, 0.8, 0.4],
        ], dtype=np.float32)
        cam = camera()
        projecao = np.eye(4, dtype=np.float32)
        projecao[3, 2] = 1.0  # w = z+1; um vértice tem w negativo
        cam.getMatrices = lambda _eye: (
            projecao, np.eye(4, dtype=np.float32)
        )
        self.assertEqual(
            selecionar_cor([original], [cam], 55, 55, 100, 100),
            (12, 34, 56),
        )
        profundidade = selecionar_profundidade(
            [original], [cam], 55, 55, 100, 100,
        )
        self.assertGreaterEqual(profundidade, 0.0)
        self.assertLess(profundidade, 1.0)
        original.cull = -1
        self.assertEqual(
            selecionar_cor([original], [cam], 55, 55, 100, 100),
            (0, 0, 0),
        )

    def test_recorte_descarta_near_far(self):
        original = objeto("fora_da_camera")
        for z in (-3.0, 3.0):
            with self.subTest(z=z):
                original.verts[:, 2] = z
                self.assertEqual(
                    selecionar_cor([original], [camera()], 50, 50, 100, 100),
                    (0, 0, 0),
                )
                self.assertEqual(
                    selecionar_profundidade([original], [camera()], 50, 50, 100, 100),
                    1.0,
                )

    def test_recorte_lateral_mantem_triangulo_visivel(self):
        original = objeto(
            "atravessa_lateral", indices=[[0, 1, 2]],
            grupos=[(0, 1)], cores=[(7, 11, 13)],
        )
        original.verts = np.array([
            [-2.5, -0.8, 0.4], [0.8, -0.8, 0.4],
            [0.0, 0.8, 0.4],
        ], dtype=np.float32)
        self.assertEqual(
            selecionar_cor([original], [camera()], 50, 50, 100, 100),
            (7, 11, 13),
        )


class TestarProfundidadeSemOpenGL(unittest.TestCase):
    def test_profundidade_usa_o_objeto_visivel_mais_perto(self):
        perto = objeto("perto", z=0.15)
        longe = objeto("longe", z=0.65)
        z = selecionar_profundidade(
            [perto, longe], [camera()], 50, 50, 100, 100,
        )
        self.assertAlmostEqual(z, (0.15 + 1) / 2, places=5)

    def test_fundo_sem_objetos_retorna_profundidade_maxima(self):
        self.assertEqual(
            selecionar_profundidade([], [camera()], 25, 25, 100, 100),
            1.0,
        )
        self.assertEqual(
            selecionar_profundidade(
                [objeto("fora")], [camera()], -1, 25, 100, 100,
            ),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
