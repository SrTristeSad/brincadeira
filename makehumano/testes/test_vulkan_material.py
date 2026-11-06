"""Regressões de parâmetros de materiais existentes na GUI original.

Não carrega OpenGL nem exige dispositivo Vulkan; o smoke de GUI em CI
valida o shader e o envio efetivo dos uniforms.
"""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))

from vulkan_material import parametros_material_vulkan


def objeto(*, cor=(0.8, 0.3, 0.2), opacidade=0.6, shadeless=False,
           solido=True, com_textura=True, caminho="pele.png"):
    return SimpleNamespace(
        material=SimpleNamespace(
            diffuseColor=SimpleNamespace(values=cor),
            opacity=opacidade,
        ),
        shadeless=shadeless,
        solid=solido,
        isTextured=com_textura,
        texture=caminho,
    )


class TestarMaterialVulkanOriginal(unittest.TestCase):
    def test_reaproveita_difusa_opacidade_e_textura_original(self):
        dados, caminho = parametros_material_vulkan(objeto())
        self.assertEqual(dados.dtype, np.float32)
        self.assertEqual(dados.shape, (8,))
        np.testing.assert_allclose(dados[:4], [0.8, 0.3, 0.2, 0.6])
        np.testing.assert_array_equal(dados[4:], [0, 0, 0, 0])
        self.assertEqual(caminho, "pele.png")

    def test_shadeless_nao_apaga_cor_ou_textura(self):
        dados, caminho = parametros_material_vulkan(objeto(shadeless=True))
        self.assertEqual(dados[4], 1.0)
        np.testing.assert_allclose(dados[:4], [0.8, 0.3, 0.2, 0.6])
        self.assertEqual(caminho, "pele.png")

    def test_iluminado_nao_ativa_flag_shadeless(self):
        dados, _ = parametros_material_vulkan(objeto(shadeless=False))
        self.assertEqual(dados[4], 0.0)

    def test_desativar_textura_na_gui_ignora_arquivo_associado(self):
        dados, caminho = parametros_material_vulkan(
            objeto(com_textura=False, caminho="arquivo_ainda_associado.png")
        )
        self.assertIsNone(caminho)
        np.testing.assert_allclose(dados[:3], [0.8, 0.3, 0.2])

    def test_objeto_nao_solido_usa_difusa_branca_sem_textura(self):
        dados, caminho = parametros_material_vulkan(objeto(
            solido=False, cor=(0.1, 0.2, 0.3), opacidade=0.2
        ))
        self.assertIsNone(caminho)
        np.testing.assert_array_equal(dados[:4], [1, 1, 1, 1])

    def test_mudar_opacidade_recalcula_uniforms(self):
        original = objeto()
        antes, _ = parametros_material_vulkan(original)
        original.material.opacity = 0.9
        depois, _ = parametros_material_vulkan(original)
        self.assertEqual(antes[3], np.float32(0.6))
        self.assertEqual(depois[3], np.float32(0.9))
        np.testing.assert_array_equal(antes[:3], depois[:3])

    def test_valores_limite_de_opacidade(self):
        for alpha in (0.0, 1.0):
            with self.subTest(alpha=alpha):
                dados, _ = parametros_material_vulkan(objeto(opacidade=alpha))
                self.assertEqual(dados[3], alpha)

    def test_caminho_vazio_equivale_a_textura_branca_do_piloto(self):
        _, caminho = parametros_material_vulkan(objeto(caminho=None))
        self.assertIsNone(caminho)

    def test_rejeita_cores_inconsistentes(self):
        for cor in ((1, 0), (1, 0, 0, 1), (np.nan, 1, 1)):
            with self.subTest(cor=cor):
                with self.assertRaises(ValueError):
                    parametros_material_vulkan(objeto(cor=cor))

    def test_rejeita_opacidade_invalida(self):
        for alpha in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(alpha=alpha):
                with self.assertRaises(ValueError):
                    parametros_material_vulkan(objeto(opacidade=alpha))

    def test_layout_uniform_esperado_pelo_wgsl(self):
        dados, _ = parametros_material_vulkan(objeto(shadeless=True))
        matriz = np.eye(4, dtype=np.float32)
        uniforms = np.concatenate((matriz.T.reshape(-1), dados))
        self.assertEqual(uniforms.shape, (24,))
        self.assertEqual(uniforms.nbytes, 96)
        self.assertEqual(uniforms[20], 1.0)


if __name__ == "__main__":
    unittest.main()
