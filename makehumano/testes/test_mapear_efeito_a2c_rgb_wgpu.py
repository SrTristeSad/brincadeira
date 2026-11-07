"""Testes CPU da interseção e proximidade espacial do efeito A2C."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapear_efeito_a2c_rgb import (
    analisar_efeitos, criar_mapa, dilatar_um_pixel, mascara_efeito,
)


class TesteMapaA2C(unittest.TestCase):
    def test_iou_e_coincidencia_de_um_pixel(self):
        blank = np.zeros((5, 5, 3), dtype=np.uint8)
        gl = blank.copy()
        vk = blank.copy()
        gl[2, 2] = (9, 0, 0)
        vk[2, 3] = (0, 9, 0)
        metrica, mg, mv = analisar_efeitos(blank, gl, blank, vk)
        self.assertEqual(metrica["pixels_intersecao"], 0)
        self.assertEqual(metrica["pixels_uniao"], 2)
        self.assertEqual(metrica["iou_localizacao_efeito"], 0)
        self.assertEqual(metrica["fracao_pixels_gl_a_ate_1px_de_vk"], 1)
        self.assertEqual(metrica["fracao_pixels_vk_a_ate_1px_de_gl"], 1)
        img = criar_mapa(mg, mv)
        self.assertEqual(img[2, 2].tolist(), [255, 75, 75])
        self.assertEqual(img[2, 3].tolist(), [35, 185, 240])

    def test_pixels_identicos_nao_inventam_diferencas(self):
        base = np.zeros((4, 4, 3), dtype=np.uint8)
        m, gl, vk = analisar_efeitos(base, base.copy(), base, base.copy())
        self.assertEqual(m["pixels_uniao"], 0)
        self.assertEqual(m["iou_localizacao_efeito"], 1)
        self.assertFalse(gl.any() or vk.any())

    def test_mascara_limiar_e_dilatacao(self):
        a = np.zeros((3, 3, 3), dtype=np.uint8)
        b = a.copy()
        b[1, 1, 0] = 8
        self.assertFalse(mascara_efeito(a, b).any())
        b[1, 1, 0] = 9
        m = mascara_efeito(a, b)
        self.assertEqual(int(m.sum()), 1)
        self.assertEqual(int(dilatar_um_pixel(m).sum()), 9)

    def test_rejeita_formato_e_resolucao(self):
        with self.assertRaises(ValueError):
            mascara_efeito(np.zeros((2, 2, 4), np.uint8),
                           np.zeros((2, 2, 4), np.uint8))
        with self.assertRaises(ValueError):
            analisar_efeitos(np.zeros((2, 2, 3), np.uint8),
                             np.zeros((2, 2, 3), np.uint8),
                             np.zeros((3, 2, 3), np.uint8),
                             np.zeros((3, 2, 3), np.uint8))


if __name__ == "__main__":
    unittest.main()
