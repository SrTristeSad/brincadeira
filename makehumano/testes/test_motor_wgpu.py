"""Verifica dados de malha e materiais sem exigir GPU ou janela."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.materiais import Pele, validar_rgba, textura_neutra


class TestarMalha(unittest.TestCase):
    def test_triangula_quad_e_separa_uv(self):
        texto = """v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
g body
f 1/1 2/2 3/3 4/4
g helper
f 1/1 4/4 3/3
"""
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "amostra.obj"
            arquivo.write_text(texto, encoding="utf-8")
            malha = carregar_obj(arquivo)
        self.assertEqual(malha.vertices.shape, (4, 8))
        self.assertEqual(malha.indices.shape, (6,))
        self.assertEqual(malha.vertices.dtype, np.float32)
        self.assertEqual(malha.indices.dtype, np.uint32)
        np.testing.assert_array_equal(malha.indices, [0, 1, 2, 0, 2, 3])
        np.testing.assert_allclose(malha.vertices[0, 6:], [0, 1])

    def test_base_obj_original_tem_triangulos_e_uv(self):
        malha = carregar_obj(caminho_base_obj())
        self.assertGreater(len(malha.vertices), 10_000)
        self.assertGreater(len(malha.indices), 25_000)
        self.assertEqual(len(malha.indices) % 3, 0)
        self.assertTrue(np.isfinite(malha.vertices).all())


class TestarMaterial(unittest.TestCase):
    def test_pele_atualiza_tom_e_rugosidade(self):
        pele = Pele()
        pele.atualizar(cor=(0.5, 0.4, 0.3), rugosidade=0.22)
        self.assertEqual(pele.cor, (0.5, 0.4, 0.3))
        self.assertAlmostEqual(pele.rugosidade, 0.22)

    def test_material_rejeita_intervalos_invalidos(self):
        with self.assertRaises(ValueError):
            Pele(cor=(1.2, 0, 0))
        with self.assertRaises(ValueError):
            Pele(rugosidade=0.0)

    def test_textura_rgba_validada(self):
        textura = validar_rgba(textura_neutra())
        self.assertEqual(textura.shape, (4, 4, 4))
        self.assertEqual(textura.dtype, np.uint8)
        self.assertTrue(textura.flags.c_contiguous)
        with self.assertRaises(ValueError):
            validar_rgba(np.zeros((3, 2, 3), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
