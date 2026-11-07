"""Testa textura de controle sem GPU, sem Pillow nem Image do MakeHuman."""
import hashlib
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textura_alpha_controle import dados_textura_alfa_parcial


class TestControleTexturaAlfa(unittest.TestCase):
    def test_rgba_parcial_e_xadrez_cor(self):
        a = dados_textura_alfa_parcial()
        self.assertEqual(a.shape, (32, 32, 4))
        self.assertEqual(a.dtype, np.uint8)
        self.assertTrue(np.all(a[:, :, 3] == 128))
        self.assertFalse(np.array_equal(a[0, 0, :3], a[0, 9, :3]))

    def test_deterministico(self):
        self.assertEqual(
            hashlib.sha256(dados_textura_alfa_parcial().tobytes()).hexdigest(),
            hashlib.sha256(dados_textura_alfa_parcial().tobytes()).hexdigest()
        )

    def test_parametros_devem_ser_pareados(self):
        with self.assertRaises(ValueError):
            dados_textura_alfa_parcial(alfa=255)
        with self.assertRaises(ValueError):
            dados_textura_alfa_parcial(lado=64)


if __name__ == "__main__":
    unittest.main()
