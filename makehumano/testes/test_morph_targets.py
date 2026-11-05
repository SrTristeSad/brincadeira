"""Testes pequenos do algoritmo de deformação 3D original, sem interface Qt."""

from pathlib import Path
import sys
import unittest

import numpy as np


RAIZ_MAKEHUMAN = Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
if not RAIZ_MAKEHUMAN.is_dir():
    raise RuntimeError("Código MakeHuman ausente: execute importar_original.py primeiro.")

# O MakeHuman original usa importações absolutas de diretórios internos.
sys.path.insert(0, str(RAIZ_MAKEHUMAN / "lib"))
sys.path.insert(0, str(RAIZ_MAKEHUMAN / "core"))

import algos3d  # noqa: E402


class MalhaSimulada:
    def __init__(self):
        self.coord = np.zeros((4, 3), dtype=np.float32)
        self.vertices_alterados = None
        self.atualizacoes = 0
        self.normais_recalculadas = 0

    def markCoords(self, indices, coor=False):
        self.vertices_alterados = np.array(indices, copy=True)

    def update(self):
        self.atualizacoes += 1

    def calcNormals(self, *_args):
        self.normais_recalculadas += 1


class TesteMorphTargets(unittest.TestCase):
    def preparar_target(self, indices, vetores):
        # Criar instância sem acessar arquivos de assets ou carregar a interface.
        target = algos3d.Target.__new__(algos3d.Target)
        target.verts = np.array(indices, dtype=np.uint32)
        target.data = np.array(vetores, dtype=np.float32).reshape((-1, 3))
        target.faces = np.array([], dtype=np.uint32)
        return target

    def test_deslocamento_escalonado_dos_vertices(self):
        malha = MalhaSimulada()
        target = self.preparar_target([0, 2], [[2, 0, 0], [0, 4, 0]])

        alterou = target.apply(
            malha, 0.5, scale=(1, 2, 1), update=False, calcNormals=False
        )

        self.assertTrue(alterou)
        np.testing.assert_allclose(
            malha.coord,
            [[1, 0, 0], [0, 0, 0], [0, 4, 0], [0, 0, 0]],
        )
        np.testing.assert_array_equal(malha.vertices_alterados, [0, 2])
        self.assertEqual(malha.atualizacoes, 0)

    def test_target_sem_vertices_nao_altera_malha(self):
        malha = MalhaSimulada()
        target = self.preparar_target([], [])

        self.assertFalse(target.apply(malha, 1.0, update=False, calcNormals=False))
        np.testing.assert_array_equal(malha.coord, np.zeros((4, 3)))
        self.assertIsNone(malha.vertices_alterados)

    def test_atualizacao_solicitada(self):
        malha = MalhaSimulada()
        target = self.preparar_target([1], [[0, 0, 2]])

        self.assertTrue(target.apply(malha, 1.0, update=True, calcNormals=True))
        self.assertEqual(malha.atualizacoes, 1)
        self.assertEqual(malha.normais_recalculadas, 1)


if __name__ == "__main__":
    unittest.main()
