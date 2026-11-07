"""Testa decomposição espacial do efeito RGB A2C sem GPU nem SciPy."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapear_efeito_a2c_rgb import (
    decompor_efeito_a2c, deslocar_mascara, erodir_mascara,
)


class TesteDecomposicaoA2C(unittest.TestCase):
    def test_translacao_diagnostica_detecta_um_pixel_sem_alterar_entrada(self):
        off_gl = np.full((11, 11, 3), 100, dtype=np.uint8)
        off_vk = np.full((11, 11, 3), 188, dtype=np.uint8)
        on_gl, on_vk = off_gl.copy(), off_vk.copy()
        on_gl[5, 5] = (110, 100, 100)
        on_vk[5, 6] = (198, 188, 188)
        before = on_gl.copy()
        res = decompor_efeito_a2c(off_gl, on_gl, off_vk, on_vk, busca_deslocamento=2)
        registro = res["busca_translacao_inteira_diagnostica"]
        self.assertEqual(registro["melhor_deslocamento_gl_para_vk_xy"], [1, 0])
        self.assertEqual(registro["iou_sem_deslocamento"], 0.0)
        self.assertEqual(registro["iou_melhor"], 1.0)
        self.assertTrue(np.array_equal(on_gl, before))
        self.assertEqual(res["fundo_rgb_off_opengl"], [100, 100, 100])
        self.assertEqual(res["fundo_rgb_off_vulkan"], [188, 188, 188])

    def test_borda_e_interior_sao_disjuntos(self):
        off_gl = np.full((13, 13, 3), 100, dtype=np.uint8)
        off_vk = np.full((13, 13, 3), 188, dtype=np.uint8)
        off_gl[2:11, 2:11] = 145
        off_vk[2:11, 2:11] = 220
        on_gl, on_vk = off_gl.copy(), off_vk.copy()
        on_gl[5, 5] = (180, 180, 180)  # interior após erosão de 2px
        on_gl[2, 5] = (180, 180, 180)  # contorno
        on_vk[5, 5] = (250, 250, 250)
        on_vk[2, 5] = (250, 250, 250)
        r = decompor_efeito_a2c(off_gl, on_gl, off_vk, on_vk, erosao_pixels=2)
        for backend in ("opengl", "vulkan"):
            d = r["borda_corpo_estimados"][backend]
            self.assertEqual(d["pixels_efeito_na_borda_ou_exterior"], 1)
            self.assertEqual(d["pixels_efeito_no_interior_estimado"], 1)
            self.assertEqual(d["pixels_efeito_fora_do_corpo_estimado"], 0)

    def test_direcao_oposta_no_mesmo_pixel(self):
        gl = np.full((7, 7, 3), 100, dtype=np.uint8)
        vk = np.full((7, 7, 3), 188, dtype=np.uint8)
        a, b = gl.copy(), vk.copy()
        a[3, 3] = (120, 120, 120)
        b[3, 3] = (168, 168, 168)
        r = decompor_efeito_a2c(gl, a, vk, b, busca_deslocamento=0)
        delta = r["direcao_dos_deltas_na_intersecao"]
        self.assertEqual(delta["pixels_suporte_conjunto"], 1)
        self.assertEqual(delta["fracao_deltas_rgb_direcao_oposta_cos_lt_menos_0_5"], 1.0)
        self.assertEqual(delta["fracao_deltas_rgb_mesma_direcao_cos_gt_0_5"], 0.0)

    def test_erosao_e_deslocamento_sem_wrap(self):
        mascara = np.ones((5, 5), dtype=bool)
        self.assertEqual(int(erodir_mascara(mascara, pixels=1).sum()), 9)
        entrada = np.zeros((5, 5), dtype=bool)
        entrada[0, 0] = True
        self.assertFalse(deslocar_mascara(entrada, -1, 0).any())
        deslocada = deslocar_mascara(entrada, 1, 1)
        self.assertTrue(deslocada[1, 1])
        self.assertEqual(int(deslocada.sum()), 1)

    def test_rejeita_formato_ou_parametros_invalidos(self):
        a = np.zeros((5, 5, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            decompor_efeito_a2c(a, a, a, np.zeros((6, 5, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            decompor_efeito_a2c(a, a, a, a, busca_deslocamento=-1)
        with self.assertRaises(ValueError):
            deslocar_mascara(np.zeros((3, 3), dtype=bool), 1.5, 0)


if __name__ == "__main__":
    unittest.main()
