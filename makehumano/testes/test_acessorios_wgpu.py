"""Valida acessórios com ligação .mhclo original sem GPU ou Qt."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.acessorios import (
    carregar_proxy_direto, caminho_olhos_lowpoly,
)
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.morphs import Deformador, Alvo


class TestarAcessorios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())
        cls.olhos = carregar_proxy_direto(caminho_olhos_lowpoly(), cls.corpo)

    def test_malha_olhos_oficial_96_vertices_com_uvs(self):
        olhos = self.olhos
        self.assertEqual(len(olhos.referencias), 96)
        self.assertTrue(olhos.textura.is_file())
        self.assertGreater(len(olhos.malha.indices), 100)
        self.assertEqual(len(olhos.malha.indices) % 3, 0)
        np.testing.assert_array_equal(
            olhos.malha.posicoes_base,
            self.corpo.posicoes_base[olhos.referencias],
        )
        self.assertTrue(np.isfinite(olhos.malha.vertices).all())
        np.testing.assert_array_equal(
            olhos.atualizar(self.corpo.posicoes_base),
            olhos.malha.vertices,
        )

    def test_olhos_seguem_target_real_em_indices_do_corpo(self):
        corpo = self.corpo
        olhos = self.olhos
        vertice_base = int(olhos.referencias[0])
        alvo = Alvo(
            indices=np.array([vertice_base], dtype=np.uint32),
            deslocamentos=np.array([[0.06, -0.03, 0.12]], dtype=np.float32),
        )
        deformador = Deformador(corpo)
        primeira = olhos.atualizar(deformador.posicoes_atuais)
        deformador.definir_peso("mover-olho", alvo, 0.5)
        atual = olhos.atualizar(deformador.posicoes_atuais)
        indice_render = np.flatnonzero(olhos.malha.origens == 0)[0]
        np.testing.assert_allclose(
            atual[indice_render, :3] - primeira[indice_render, :3],
            [0.03, -0.015, 0.06], atol=1e-6,
        )
        np.testing.assert_array_equal(atual[:, 6:8], primeira[:, 6:8])
        self.assertFalse(np.array_equal(atual[:, 3:6], primeira[:, 3:6]))
        deformador.restaurar()
        np.testing.assert_allclose(
            olhos.atualizar(deformador.posicoes_atuais), primeira,
            atol=1e-6,
        )

    def test_nao_confunde_proxy_complexo_com_mapeamento_direto(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            (tmp / "olho.obj").write_text(
                "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
                "vt 0 0\nvt 1 0\nvt 0 1\n"
                "f 1/1 2/2 3/3\n", encoding="utf-8",
            )
            proxy = tmp / "olho.mhclo"
            proxy.write_text(
                "obj_file olho.obj\nverts 0\n"
                "1 2 3 0.3 0.4 0.3 0 0 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "interpolado"):
                carregar_proxy_direto(proxy, self.corpo)

    def test_rejeita_indice_fora_do_corpo_e_caminho_externo(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            proxy = tmp / "estranho.mhclo"
            proxy.write_text(
                "obj_file ../segredo.obj\nverts 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "local"):
                carregar_proxy_direto(proxy, self.corpo)
            proxy.write_text(
                "obj_file olho.obj\nverts 0\n999999\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "fora do corpo"):
                carregar_proxy_direto(proxy, self.corpo)


if __name__ == "__main__":
    unittest.main()
