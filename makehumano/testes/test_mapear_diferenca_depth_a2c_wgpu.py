"""Regressões CPU do diagnóstico de escrita Z; não precisa de GPU."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapear_diferenca_depth_a2c import (
    analisar_profundidade, componentes_8_conexos, gerar_overlay,
)


class TesteDiferencaDepth(unittest.TestCase):
    def test_componentes_diagonais_e_caixas(self):
        m = np.zeros((7, 8), dtype=bool)
        m[1, 1] = True
        m[2, 2] = True  # conexo pela diagonal
        m[5, 6] = True
        c = componentes_8_conexos(m)
        self.assertEqual([v["pixels"] for v in c], [2, 1])
        self.assertEqual(c[0]["bbox_xyxy"], [1, 1, 2, 2])
        self.assertEqual(c[1]["bbox_xyxy"], [6, 5, 6, 5])

    def test_localizacao_e_classificacao_de_malha(self):
        base = np.full((11, 11, 3), 128, dtype=np.uint8)
        base[2:9, 2:9] = 190
        with_depth = base.copy()
        with_depth[5, 5] = 211
        with_depth[2, 5] = 211
        d, mask = analisar_profundidade(base, with_depth, erosao_pixels=1)
        self.assertEqual(d["pixels_alterados_gt_tolerancia"], 2)
        self.assertEqual(d["pixels_no_interior_estimado"], 1)
        self.assertEqual(d["pixels_na_faixa_de_borda_ou_exterior"], 1)
        self.assertEqual(d["pixels_fora_da_silhueta_estimada"], 0)
        self.assertEqual(d["max_delta_canal_rgb"], 21)
        self.assertEqual(int(mask.sum()), 2)
        image = gerar_overlay(base, mask)
        self.assertEqual(image[5, 5].tolist(), [255, 40, 40])
        self.assertEqual(image[0, 0].tolist(), [128, 128, 128])
        self.assertTrue(np.array_equal(base[5, 5], np.array([190]*3)))

    def test_imagens_identicas_sem_falso_positivo(self):
        a = np.full((8, 8, 3), 188, dtype=np.uint8)
        d, m = analisar_profundidade(a, a.copy())
        self.assertEqual(d["pixels_alterados_gt_tolerancia"], 0)
        self.assertEqual(d["pixels_alterados_qualquer_delta"], 0)
        self.assertIsNone(d["bbox_total_xyxy"])
        self.assertEqual(d["quantidade_componentes_8_conexos"], 0)
        self.assertFalse(m.any())

    def test_limiar_exclui_diferencas_pequenas(self):
        a = np.zeros((6, 6, 3), dtype=np.uint8)
        b = a.copy()
        b[2, 2] = (8, 0, 0)
        d, _ = analisar_profundidade(a, b)
        self.assertEqual(d["pixels_alterados_gt_tolerancia"], 0)
        self.assertEqual(d["pixels_alterados_qualquer_delta"], 1)

    def test_rejeita_mascara_incompatível(self):
        with self.assertRaises(ValueError):
            componentes_8_conexos(np.zeros((3, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            gerar_overlay(np.zeros((3, 3, 3), dtype=np.uint8),
                          np.zeros((4, 4), dtype=bool))


if __name__ == "__main__":
    unittest.main()
