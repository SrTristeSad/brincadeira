"""Regressões para o catálogo de modificadores com configurações oficiais."""

from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.modificadores import carregar_catalogo
from motor_wgpu.morphs import Alvo, Deformador, ler_target


class TestarCatalogo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = carregar_catalogo()
        cls.malha = carregar_obj(caminho_base_obj())

    def test_catalogo_vem_das_definicoes_oficiais(self):
        self.assertGreaterEqual(len(self.catalogo), 230)
        self.assertEqual(len({m.identificador for m in self.catalogo}), len(self.catalogo))
        self.assertGreaterEqual(len({m.grupo for m in self.catalogo}), 15)
        for modificador in self.catalogo:
            self.assertTrue(modificador.positivo.is_file())
            if modificador.negativo:
                self.assertTrue(modificador.negativo.is_file())

    def test_bilateral_encaminha_pesos_para_cada_direcao(self):
        nariz = next(
            item for item in self.catalogo
            if item.identificador == "nose/nose-scale-horiz-decr|incr"
        )
        self.assertEqual(nariz.minimo, -100)
        ps = nariz.pesos(65)
        self.assertAlmostEqual(ps[nariz.positivo], 0.65)
        self.assertAlmostEqual(ps[nariz.negativo], 0)
        ns = nariz.pesos(-35)
        self.assertAlmostEqual(ns[nariz.positivo], 0)
        self.assertAlmostEqual(ns[nariz.negativo], 0.35)
        with self.assertRaises(ValueError):
            nariz.pesos(-101)

    def test_unilateral_comeca_em_zero(self):
        item = next(m for m in self.catalogo if m.negativo is None)
        self.assertEqual(item.minimo, 0)
        self.assertEqual(item.pesos(80), {item.positivo: 0.8})
        with self.assertRaises(ValueError):
            item.pesos(-1)

    def test_morph_real_muda_de_direcao_sem_acumular(self):
        nariz = next(
            item for item in self.catalogo
            if item.identificador == "nose/nose-scale-horiz-decr|incr"
        )
        alvos = {}
        for arquivo in [nariz.negativo, nariz.positivo]:
            alvos[str(arquivo)] = ler_target(arquivo, len(self.malha.posicoes_base))
        deformador = Deformador(self.malha)

        def aplicar(valor):
            return deformador.definir_pesos({
                str(path): (alvos[str(path)], peso)
                for path, peso in nariz.pesos(valor).items()
            }).copy()

        maior = aplicar(60)
        menor = aplicar(-40)
        self.assertGreater(
            np.max(np.abs(maior[:, :3] - menor[:, :3])), 0.001
        )
        np.testing.assert_array_equal(maior, aplicar(60))
        np.testing.assert_allclose(deformador.restaurar(), self.malha.vertices, atol=1e-5)

    def test_atualizacao_invalida_nao_altera_pesos(self):
        vazio = Alvo(np.array([0], np.uint32), np.array([[0, 0, 1]], np.float32))
        deformador = Deformador(self.malha)
        esperado = deformador.definir_peso("base", vazio, 0.2).copy()
        with self.assertRaises(ValueError):
            deformador.definir_pesos({
                "base": (vazio, 0.9),
                "invalido": (vazio, 1.5),
            })
        np.testing.assert_array_equal(esperado, deformador.reconstruir())


if __name__ == "__main__":
    unittest.main()
