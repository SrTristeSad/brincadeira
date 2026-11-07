"""Regressões CPU para não confundir máscara API com RGBA opaco artificial."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from registrar_mascara_paridade import extrair_mascara_api
from comparar_mascara_paridade import metricas_alfa


class TestarMascaraAlfa(unittest.TestCase):
    def setUp(self):
        self.array = np.zeros((768, 1024, 3), dtype=np.uint8)
        self.array[120:620, 280:680] = 255

    def test_preserva_valor_em_alfa_e_rgb_zero(self):
        rgba, info = extrair_mascara_api(SimpleNamespace(data=self.array))
        self.assertTrue(np.all(rgba[:, :, :3] == 0))
        self.assertEqual(int(rgba[0, 0, 3]), 0)
        self.assertEqual(int(rgba[200, 400, 3]), 255)
        self.assertEqual(info["alfa_nao_zero"], 500 * 400)

    def test_rejeita_imagem_colorida(self):
        self.array[120, 280, 0] = 3
        with self.assertRaises(ValueError):
            extrair_mascara_api(SimpleNamespace(data=self.array))

    def test_rejeita_cobertura_trivial(self):
        for n in (0, 255):
            with self.assertRaises(ValueError):
                extrair_mascara_api(
                    SimpleNamespace(data=np.full_like(self.array, n))
                )

    def test_alpha_identico_satisfaz_limites(self):
        alpha = self.array[:, :, 0]
        m = metricas_alfa(alpha, alpha.copy())
        self.assertEqual(m["iou_cobertura_alfa_real"], 1.0)
        self.assertEqual(m["fracao_alfa_fora_tolerancia_8"], 0.)
        self.assertTrue(m["limiares_mascara_propostos_atendidos"])

    def test_alfa_parcial_igual(self):
        a = self.array[:, :, 0].copy()
        a[a == 255] = 128
        met = metricas_alfa(a, a.copy())
        self.assertEqual(met["pixels_alfa_parciais_opengl"], 200000)
        self.assertEqual(met["pixels_alfa_parciais_vulkan"], 200000)
        self.assertEqual(met["fracao_alfa_fora_tolerancia_8"], 0.)

    def test_alfa_parcial_diferente_detectado(self):
        a = self.array[:, :, 0].copy()
        b = a.copy()
        a[a == 255] = 128
        b[b == 255] = 192
        met = metricas_alfa(a, b)
        self.assertEqual(met["iou_cobertura_alfa_real"], 1.)
        self.assertGreater(met["fracao_alfa_fora_tolerancia_8"], 0.)
        self.assertFalse(met["limiares_mascara_propostos_atendidos"])

    def test_deslocamento_muda_iou(self):
        a = self.array[:, :, 0]
        b = np.roll(a, 60, axis=1)
        m = metricas_alfa(a, b)
        self.assertLess(m["iou_cobertura_alfa_real"], 0.995)
        self.assertFalse(m["limiares_mascara_propostos_atendidos"])


if __name__ == "__main__":
    unittest.main()
