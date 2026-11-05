"""Regressões para morph targets MakeHuman na nova malha Vulkan.

Testes independentes de wgpu/Qt para garantir números, UVs e reversibilidade.
"""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.morphs import Alvo, Deformador, ler_target, pasta_targets


class TestarMorphs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.malha_original = carregar_obj(caminho_base_obj())

    def _obj_com_costura(self):
        texto = """v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vt 0.5 0.5
g body
f 1/1 2/2 3/3
f 1/5 3/3 4/4
"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "costura.obj"
            caminho.write_text(texto, encoding="utf-8")
            return carregar_obj(caminho)

    def test_costura_uv_permanece_coesa_apos_deformacao(self):
        malha = self._obj_com_costura()
        self.assertEqual(len(np.flatnonzero(malha.origens == 0)), 2)
        uv_original = malha.vertices[:, 6:8].copy()
        alvo = Alvo(
            indices=np.array([0], dtype=np.uint32),
            deslocamentos=np.array([[0.0, 0.0, 1.0]], dtype=np.float32),
        )
        deformador = Deformador(malha)
        depois = deformador.definir_peso("subir", alvo, 0.5)
        duplicados = np.flatnonzero(malha.origens == 0)
        np.testing.assert_allclose(depois[duplicados, :3], [[0, 0, 0.5], [0, 0, 0.5]])
        np.testing.assert_allclose(
            depois[duplicados[0], 3:6], depois[duplicados[1], 3:6]
        )
        np.testing.assert_array_equal(depois[:, 6:8], uv_original)
        self.assertFalse(np.array_equal(depois[:, 3:6], malha.vertices[:, 3:6]))

    def test_mesmo_peso_nao_acumula_e_zero_restaura(self):
        malha = self._obj_com_costura()
        alvo = Alvo(
            indices=np.array([0], dtype=np.uint32),
            deslocamentos=np.array([[0.0, 0.2, 0.3]], dtype=np.float32),
        )
        deformador = Deformador(malha)
        primeiro = deformador.definir_peso("teste", alvo, 0.8).copy()
        segundo = deformador.definir_peso("teste", alvo, 0.8).copy()
        np.testing.assert_array_equal(primeiro, segundo)
        deformador.definir_peso("teste", alvo, 0.0)
        np.testing.assert_allclose(deformador.vertices, malha.vertices, atol=1e-6)

    def test_combinacao_de_alvos_e_restaurar(self):
        malha = self._obj_com_costura()
        a = Alvo(np.array([0], np.uint32), np.array([[1, 0, 0]], np.float32))
        b = Alvo(np.array([0], np.uint32), np.array([[0, 1, 0]], np.float32))
        deformador = Deformador(malha)
        deformador.definir_peso("a", a, 0.5)
        atual = deformador.definir_peso("b", b, 0.25)
        np.testing.assert_allclose(atual[malha.origens == 0, :3], [[0.5, 0.25, 0], [0.5, 0.25, 0]])
        np.testing.assert_allclose(deformador.restaurar(), malha.vertices, atol=1e-6)

    def test_target_original_altera_o_corpo_e_volta_ao_inicio(self):
        malha = self.malha_original
        alvo = ler_target(
            pasta_targets() / "nose/nose-scale-horiz-incr.target",
            len(malha.posicoes_base),
        )
        self.assertGreater(len(alvo.indices), 20)
        deformador = Deformador(malha)
        resultado = deformador.definir_peso("nariz", alvo, 0.75).copy()
        self.assertGreater(np.abs(resultado[:, :3] - malha.vertices[:, :3]).max(), 0.001)
        self.assertTrue(np.isfinite(resultado).all())
        np.testing.assert_allclose(deformador.restaurar(), malha.vertices, atol=1e-5)

    def test_rejeita_indice_invalido_e_peso_ilegal(self):
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = Path(tmp) / "quebrado.target"
            arquivo.write_text("# licença\n99999 0.1 0 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "índice fora da malha"):
                ler_target(arquivo, 4)
        alvo = Alvo(np.array([0], np.uint32), np.array([[0, 0, 1]], np.float32))
        deformador = Deformador(self._obj_com_costura())
        with self.assertRaises(ValueError):
            deformador.definir_peso("x", alvo, float("nan"))
        with self.assertRaises(ValueError):
            deformador.definir_peso("x", alvo, -1)


if __name__ == "__main__":
    unittest.main()
