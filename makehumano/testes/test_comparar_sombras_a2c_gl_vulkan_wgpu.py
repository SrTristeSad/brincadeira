"""Regressões CPU do controle de sombras sem confundir cor com A2C.

Não precisa GPU/Qt. Os cenários também verificam que uma medição pode
piorar após desligar sombras: a ferramenta não deve falsificar melhora.
"""
import copy
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comparar_sombras_a2c_gl_vulkan import (
    auditar_controles, intersecao_sobre_uniao, medir_efeito_sombras,
)
from test_comparar_a2c_backends_wgpu import modelos


def criar_fixture():
    gl, vk = modelos()
    for nome, esperado_a2c in (
        ("4x_sem_a2c", False), ("4x_com_a2c", True),
    ):
        c = vk["controles"][nome]
        c["controle_sombras_desligadas"] = False
        c["recebe_sombras_material_observado"] = True
        for d in c["rastros_pipeline_corpo"]:
            d["recebe_sombras_material_observado"] = True
        c_sem = copy.deepcopy(c)
        c_sem["controle_sombras_desligadas"] = True
        c_sem["recebe_sombras_material_observado"] = False
        for d in c_sem["rastros_pipeline_corpo"]:
            d["recebe_sombras_material_observado"] = False
        vk["controles"][nome + "_sem_sombras"] = c_sem
    pareamento = {"estado": "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS"}
    return gl, vk, pareamento


class TesteComparacaoSombras(unittest.TestCase):
    def setUp(self):
        self.base = np.zeros((9, 9, 3), np.uint8)

    def alterar(self, coord):
        a = self.base.copy()
        a[coord] = [21, 21, 21]
        return a

    def test_isolamento_recupera_coincidencia_sem_impor_resultado(self):
        gl_off = self.base
        gl_on = self.alterar((4, 4))
        vk_off = self.base
        vk_on = self.alterar((5, 4))
        vk_sem_off = self.base
        vk_sem_on = self.alterar((4, 4))
        res, masks = medir_efeito_sombras(
            gl_off, gl_on, vk_off, vk_on, vk_sem_off, vk_sem_on
        )
        self.assertEqual(
            res["comparacao_a2c_gl_vk_com_sombras"]["iou"], 0.
        )
        self.assertEqual(
            res["comparacao_a2c_gl_vk_sem_sombras"]["iou"], 1.
        )
        self.assertEqual(res["pixels_efeito_a2c_vk_sem_sombras"], 1)
        self.assertTrue(masks["vk_sem_sombras"][4, 4])
        self.assertTrue(res["nao_homologado"])

    def test_desligar_sombras_pode_diminuir_concordancia(self):
        m, _ = medir_efeito_sombras(
            self.base, self.alterar((4, 4)),
            self.base, self.alterar((4, 4)),
            self.base, self.alterar((5, 4)),
        )
        self.assertEqual(m["comparacao_a2c_gl_vk_com_sombras"]["iou"], 1)
        self.assertEqual(m["comparacao_a2c_gl_vk_sem_sombras"]["iou"], 0)

    def test_mascara_vazia_e_erros_de_contrato(self):
        m, _ = medir_efeito_sombras(*([self.base] * 6))
        self.assertEqual(m["comparacao_a2c_gl_vk_com_sombras"]["iou"], 1)
        self.assertEqual(m["pixels_efeito_a2c_gl"], 0)
        with self.assertRaises(ValueError):
            medir_efeito_sombras(*([self.base] * 5), self.base[:, :, :2])
        with self.assertRaises(ValueError):
            intersecao_sobre_uniao(np.zeros((3, 3), bool), np.zeros((2, 3), bool))

    def test_aceita_estados_observados_e_pareamento(self):
        auditar_controles(*criar_fixture())

    def test_rejeita_recebimento_de_sombras_ativo_no_controle(self):
        gl, vk, p = criar_fixture()
        vk["controles"]["4x_com_a2c_sem_sombras"][
            "recebe_sombras_material_observado"
        ] = True
        with self.assertRaisesRegex(ValueError, "Estado de draw"):
            auditar_controles(gl, vk, p)

    def test_rejeita_blend_alterado_ao_desligar_sombras(self):
        gl, vk, p = criar_fixture()
        vk["controles"]["4x_sem_a2c_sem_sombras"][
            "blend_habilitado_observado"
        ] = False
        with self.assertRaisesRegex(ValueError, "Estado de draw"):
            auditar_controles(gl, vk, p)

    def test_rejeita_sombra_ativa_no_spy_do_draw(self):
        gl, vk, p = criar_fixture()
        vk["controles"]["4x_sem_a2c_sem_sombras"][
            "rastros_pipeline_corpo"
        ][0]["recebe_sombras_material_observado"] = True
        with self.assertRaisesRegex(ValueError, "Spy de estado"):
            auditar_controles(gl, vk, p)

    def test_rejeita_camera_ou_textura_diferentes(self):
        gl, vk, p = criar_fixture()
        vk["camera"]["fov"] = 51
        with self.assertRaisesRegex(ValueError, "Câmeras"):
            auditar_controles(gl, vk, p)
        gl, vk, p = criar_fixture()
        vk["textura_controle"]["sha256_png"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "Textura"):
            auditar_controles(gl, vk, p)

    def test_rejeita_relatorio_sem_pareamento_anterior(self):
        gl, vk, p = criar_fixture()
        p["estado"] = "NAO_TESTAVEL_OPENGL_4X"
        with self.assertRaisesRegex(ValueError, "Pareamento"):
            auditar_controles(gl, vk, p)


if __name__ == "__main__":
    unittest.main()
