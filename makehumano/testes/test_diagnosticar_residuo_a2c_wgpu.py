"""Teste CPU do diagnóstico do resíduo GL/Vulkan após normalizar sombras."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosticar_residuo_a2c import (
    caracterizar_residuo, diagnosticar, dilatar_quadrado,
    magnitudes_opostas, mapa_residuo,
)


class TesteResiduoA2C(unittest.TestCase):
    def test_distancia_chebyshev_conta_proximos_e_isolados(self):
        gl = np.zeros((14, 14), dtype=bool)
        vk = np.zeros_like(gl)
        gl[4, 4] = True
        gl[4, 5] = True
        gl[10, 10] = True  # 6px da máscara VK mais próxima
        vk[4, 4] = True
        vk[4, 6] = True
        vk[1, 12] = True  # distante
        d, layers = caracterizar_residuo(gl, vk)
        self.assertEqual(d["pixels_intersecao"], 1)
        self.assertEqual(d["pixels_exclusivos_gl"], 2)
        self.assertEqual(d["pixels_exclusivos_vk"], 2)
        self.assertEqual(d["vizinhança"]["1"]["total_proximos"], 2)
        self.assertEqual(d["vizinhança"]["5"]["total_distantes"], 2)
        self.assertTrue(layers["gl_distante"][10, 10])
        self.assertTrue(layers["vk_distante"][1, 12])
        self.assertEqual(d["aglomerados_distantes"]["gl"][0]["bbox_xyxy"],
                         [10, 10, 10, 10])
        image = mapa_residuo(layers)
        self.assertEqual(image[4, 4].tolist(), [185, 185, 185])
        self.assertEqual(image[10, 10].tolist(), [255, 75, 75])
        self.assertEqual(image[1, 12].tolist(), [35, 235, 255])

    def test_sem_wraparound_na_vizinhanca(self):
        m = np.zeros((8, 8), dtype=bool)
        m[0, 0] = True
        d = dilatar_quadrado(m, 1)
        self.assertEqual(int(d.sum()), 4)
        self.assertFalse(d[7, 7])
        self.assertTrue(d[1, 1])
        self.assertEqual(int(dilatar_quadrado(m, 0).sum()), 1)

    def test_vizinhanças_monotonicas_e_mascaras_vazias(self):
        gl = np.zeros((8, 8), dtype=bool)
        vk = np.zeros_like(gl)
        gl[4, 4] = True
        vk[4, 6] = True
        d, _ = caracterizar_residuo(gl, vk)
        self.assertEqual(d["vizinhança"]["1"]["total_proximos"], 0)
        self.assertEqual(d["vizinhança"]["2"]["total_proximos"], 2)
        self.assertEqual(d["vizinhança"]["5"]["total_distantes"], 0)
        d, _ = caracterizar_residuo(np.zeros_like(gl), np.zeros_like(vk))
        self.assertEqual(d["pixels_exclusivos_total"], 0)
        self.assertEqual(d["aglomerados_distantes"]["gl"], [])

    def test_limiar_e_magnitude_oposta(self):
        zero = np.zeros((12, 12, 3), dtype=np.uint8)
        gl_on = zero.copy()
        vk_on = zero.copy()
        gl_on[4, 4] = (20, 0, 0)
        vk_on[4, 4] = (8, 0, 0)  # GL exclusiva >8, VK muda mas fica sob limiar
        vk_on[5, 5] = (0, 20, 0)  # Vulkan exclusivo
        gl_on[5, 5] = (0, 4, 0)
        gl_mask = np.any(gl_on > 8, axis=2)
        vk_mask = np.any(vk_on > 8, axis=2)
        _, layers = caracterizar_residuo(gl_mask, vk_mask)
        m = magnitudes_opostas(zero, gl_on, zero, vk_on, layers)
        self.assertEqual(m["exclusivos_gl_magnitude_vulkan"]["outro_delta_5_a_8"], 1)
        self.assertEqual(m["exclusivos_vk_magnitude_opengl"]["outro_delta_1_a_4"], 1)

    def test_varredura_muda_ao_mudar_limiar(self):
        zero = np.zeros((12, 12, 3), dtype=np.uint8)
        gl_on = zero.copy()
        vk_on = zero.copy()
        gl_on[5, 5] = [9, 9, 9]
        vk_on[5, 5] = [6, 6, 6]
        doc, maps = diagnosticar(zero, gl_on, zero, vk_on, zero, vk_on)
        self.assertEqual(doc["resultados"]["sem_sombras_limiar_8"][
            "exclusivos_total"], 1)
        self.assertEqual(doc["resultados"]["sem_sombras_limiar_4"]["iou"], 1)
        self.assertEqual(doc["resultados"]["sem_sombras_limiar_12"]["exclusivos_total"], 0)
        self.assertEqual(maps["sem_sombras"].shape, (12, 12, 3))
        self.assertTrue(doc["nao_homologado"])

    def test_rejeita_formatos_e_raios_invalidos(self):
        mask = np.zeros((4, 4), dtype=bool)
        with self.assertRaises(ValueError):
            dilatar_quadrado(mask.astype(np.uint8), 1)
        with self.assertRaises(ValueError):
            dilatar_quadrado(mask, -1)
        with self.assertRaises(ValueError):
            caracterizar_residuo(mask, mask, raios=(2, 1))
        with self.assertRaises(ValueError):
            caracterizar_residuo(mask, np.zeros((5, 4), dtype=bool))
        with self.assertRaises(ValueError):
            diagnosticar(*([np.zeros((3, 3, 4), dtype=np.uint8)] * 6))


if __name__ == "__main__":
    unittest.main()
