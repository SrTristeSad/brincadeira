"""Regressões numéricas do comparador de referência OpenGL/Vulkan."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comparar_opengl_vulkan import comparar_pixels


class TestarParidadeVisualRGBA(unittest.TestCase):
    def setUp(self):
        self.ref = np.zeros((2, 2, 4), dtype=np.uint8)

    def test_pixels_identicos_aprovados(self):
        resultado = comparar_pixels(self.ref, self.ref.copy(), fracao_maxima=0)
        self.assertTrue(resultado["aprovado"])
        self.assertEqual(resultado["erro_maximo_rgba"], 0)
        self.assertEqual(resultado["intersecao_uniao_cobertura_alfa"], 1.0)

    def test_um_pixel_fora_tolerancia_reprova_fracao(self):
        vulkan = self.ref.copy()
        vulkan[0, 1, 0] = 4
        resultado = comparar_pixels(
            self.ref, vulkan, tolerancia=3, fracao_maxima=0.24,
        )
        self.assertFalse(resultado["aprovado"])
        self.assertEqual(resultado["pixels_fora_tolerancia"], 1)
        self.assertAlmostEqual(resultado["fracao_divergente"], 0.25)
        self.assertEqual(resultado["erro_maximo_rgba"], 4)
        self.assertAlmostEqual(resultado["erro_medio_rgb"], 4.0 / 12.0)
        self.assertTrue(comparar_pixels(
            self.ref, vulkan, tolerancia=4, fracao_maxima=0,
        )["aprovado"])

    def test_alpha_nao_pode_ser_ignorado(self):
        a = self.ref.copy()
        b = self.ref.copy()
        a[0, 0, 3] = 255
        b[0, 1, 3] = 255
        resultado = comparar_pixels(a, b, tolerancia=0, fracao_maxima=0.5)
        self.assertEqual(resultado["pixels_alfa_diferente"], 2)
        self.assertEqual(resultado["pixels_fora_tolerancia"], 2)
        self.assertAlmostEqual(resultado["intersecao_uniao_cobertura_alfa"], 0)
        self.assertTrue(resultado["aprovado"])
        self.assertFalse(comparar_pixels(
            a, b, tolerancia=0, fracao_maxima=0.49,
        )["aprovado"])

    def test_tamanho_formato_e_limites_incorretos_sao_erros(self):
        with self.assertRaisesRegex(ValueError, "dimensões diferentes"):
            comparar_pixels(self.ref, np.zeros((3, 2, 4), dtype=np.uint8))
        with self.assertRaisesRegex(ValueError, "RGBA uint8"):
            comparar_pixels(self.ref.astype(np.float32), self.ref)
        with self.assertRaisesRegex(ValueError, "Tolerância"):
            comparar_pixels(self.ref, self.ref, tolerancia=-1)
        with self.assertRaisesRegex(ValueError, "Fração"):
            comparar_pixels(self.ref, self.ref, fracao_maxima=1.1)


if __name__ == "__main__":
    unittest.main()
