"""Contrato CPU do teste RGBA de upload, sem Qt/GPU reais."""
import hashlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditar_alpha_textura_gpu import SHADER_DE_PROVA, dados_cpu_alpha
from textura_alpha_controle import dados_textura_alfa_parcial


class TesteAuditoriaTexturaGPU(unittest.TestCase):
    def setUp(self):
        self.valores = {
            alpha: dados_textura_alfa_parcial(alfa=alpha)
            for alpha in (64, 128, 192)
        }
        self.caminhos = {
            alpha: f"/tmp/auditoria-controle-{alpha}.png"
            for alpha in self.valores
        }

    def _mock_loader(self, valores):
        modulo = ModuleType("vulkan_texture")
        modulo.getTexture = lambda path: SimpleNamespace(
            data=valores[int(path.rsplit("-", 1)[-1][:-4])]
        )
        return mock.patch.dict(sys.modules, {"vulkan_texture": modulo})

    def test_rgba_rgb_cpu_idêntico_para_alfas_diferentes(self):
        with self._mock_loader(self.valores):
            d = dados_cpu_alpha(self.caminhos)
        self.assertEqual(set(d), {"64", "128", "192"})
        self.assertEqual(len({d[k]["sha256_rgb"] for k in d}), 1)
        self.assertEqual(len({d[k]["sha256_rgba"] for k in d}), 3)
        self.assertEqual([d[str(i)]["alfa_min"] for i in (64, 128, 192)],
                         [64, 128, 192])

    def test_rejeita_rgb_premultiplicado_ou_modificado_no_loader(self):
        alteradas = {k: v.copy() for k, v in self.valores.items()}
        alteradas[64][:, :, :3] = (
            alteradas[64][:, :, :3].astype(np.uint16) * 64 // 255
        ).astype(np.uint8)
        with self._mock_loader(alteradas):
            with self.assertRaisesRegex(RuntimeError, "divergiu"):
                dados_cpu_alpha(self.caminhos)

    def test_rejeita_alpha_incorreto_no_loader(self):
        alteradas = {k: v.copy() for k, v in self.valores.items()}
        alteradas[192][:, :, 3] = 191
        with self._mock_loader(alteradas):
            with self.assertRaisesRegex(RuntimeError, "divergiu"):
                dados_cpu_alpha(self.caminhos)

    def test_shader_da_prova_nao_modula_rgb_por_alpha(self):
        self.assertIn("return vec4<f32>(pixel.rgb, pixel.a)", SHADER_DE_PROVA)
        self.assertNotIn("pixel.rgb * pixel.a", SHADER_DE_PROVA)


if __name__ == "__main__":
    unittest.main()
