"""Regressões CPU para duas faces cujo depth cruza no interior.

Fixtures são PNGs reais com hashes conferidos pelo comparador. Os testes
não forçam equivalência absoluta de RGB entre GL e Vulkan, apenas o
contrato geométrico, estados, Z, probes e repetibilidade.
"""
import sys
import tempfile
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato_cruzamento_depth_sintetica import (
    CASOS_CRUZAMENTO, PROBES_YX, classe_esperada,
    regioes_analiticas, registrar, passos, vertices,
)
from comparar_cruzamento_depth_sintetica import (
    auditar_manifesto, comparar_cenas, mascaras_direcao_rgb,
    salvar_mapa_categorias,
)


class TesteCruzamentoDepth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gl = self._manifesto("OpenGL")
        self.vk = self._manifesto("Vulkan")

    def _imagem(self, a2c, z_write, ordem):
        regioes = regioes_analiticas()
        imagem = np.zeros((64, 64, 3), np.uint8)
        interior = regioes["interior_seguranca"]
        imagem[interior] = (0, 0, 255)
        vermelho = regioes["vermelho_mais_perto"]
        if not z_write and ordem == "vermelho_primeiro":
            vermelho = np.zeros((64, 64), bool)
        imagem[vermelho] = (128, 0, 127) if a2c else (255, 0, 0)
        return imagem

    def _manifesto(self, backend):
        controles = {}
        for caso in CASOS_CRUZAMENTO:
            nome, a2c, z_write, ordem = caso
            imagem = self._imagem(a2c, z_write, ordem)
            png = Path(self.tmp.name) / (backend + "-" + nome + ".png")
            dados = registrar(
                imagem, png, caso, passos(a2c, z_write, ordem)
            )
            if backend == "OpenGL":
                dados.update({
                    "amostras_fbo_observadas": 4,
                    "formato_depth_fbo": "depth24",
                    "depth_range": [0.0, 1.0],
                })
            else:
                dados.update({
                    "formato_depth_pipeline": "depth24plus",
                    "amostras_depth_configuradas": 4,
                })
            controles[nome] = dados
        return {
            "backend": backend,
            "tipo": "CRUZAMENTO_DEPTH_MSAA4X",
            "controles": controles,
            "nao_homologado": True,
        }

    def test_regioes_analiticas_e_probes(self):
        r = regioes_analiticas()
        self.assertGreater(int(r["faixa_cruzamento"].sum()), 0)
        self.assertGreater(int(r["vermelho_mais_perto"].sum()), 0)
        self.assertGreater(int(r["azul_mais_perto"].sum()), 0)
        self.assertTrue(r["vermelho_mais_perto"][32, 32])
        self.assertTrue(r["azul_mais_perto"][42, 45])
        self.assertEqual(len(PROBES_YX), 2)
        self.assertEqual(vertices("vermelho")[0][2], 0.3)
        self.assertEqual(vertices("vermelho")[1][2], 0.7)
        with self.assertRaises(ValueError):
            vertices("verde")
        with self.assertRaises(ValueError):
            passos(True, False, "outro")

    def test_controles_validos_e_escrita_z(self):
        rel, _, _, masks = comparar_cenas(self.gl, self.vk)
        self.assertTrue(rel["nao_homologado"])
        self.assertEqual(rel["gl_vs_vulkan"][
            "on_z_on_vermelho_primeiro"]["pixels_rgb_diferentes"], 0)
        self.assertGreater(rel["efeitos_intrabackend"]["OpenGL"][
            "on"]["pixels_alterados_z_on_vs_off"], 0)
        self.assertTrue(masks[("OpenGL", "on")][32, 32])
        self.assertEqual(rel["efeitos_intrabackend"]["Vulkan"][
            "on"]["pixels_ordenacao_interior_fora_faixa"], 0)

    def test_rejeita_spy_de_escrita_z_incorreto(self):
        c = self.vk["controles"]["on_z_off_vermelho_primeiro"]
        c["rastros"][0]["escrita_z"] = True
        with self.assertRaisesRegex(ValueError, "Estados do draw"):
            auditar_manifesto(self.vk, "Vulkan")

    def test_rejeita_cores_de_probes_corrompidas(self):
        c = self.gl["controles"]["off_z_on_vermelho_primeiro"]
        c["probes_rgb"][0] = [0, 0, 255]
        with self.assertRaisesRegex(ValueError, "Bytes RGB"):
            auditar_manifesto(self.gl, "OpenGL")

    def test_rejeita_hash_png_invalido(self):
        c = self.vk["controles"]["off_z_on_azul_primeiro"]
        c["sha256_png"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "Hash do PNG"):
            auditar_manifesto(self.vk, "Vulkan")

    def test_rejeita_amostras_fbo_falsas(self):
        c = self.gl["controles"]["on_z_on_azul_primeiro"]
        c["amostras_fbo_observadas"] = 1
        with self.assertRaisesRegex(ValueError, "FBO"):
            auditar_manifesto(self.gl, "OpenGL")

    def test_repeticao_deve_ser_idêntica(self):
        c = self.gl["controles"]["on_z_on_repeticao"]
        c["sha256_rgb"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "Bytes RGB"):
            auditar_manifesto(self.gl, "OpenGL")

    def test_mapa_rgb_nao_confunde_direcao_com_efeito_de_z(self):
        gl = np.zeros((64, 64, 3), np.uint8)
        vk = gl.copy()
        gl[4, 4] = [191, 0, 64]
        vk[4, 4] = [128, 0, 128]  # R maior GL, B maior VK
        gl[4, 5] = [64, 0, 191]
        vk[4, 5] = [128, 0, 128]
        gl[4, 6] = [0, 0, 128]  # desempate pelo B
        vk[4, 6] = [0, 0, 255]
        gl_mask, vk_mask = mascaras_direcao_rgb(gl, vk)
        self.assertFalse(np.any(gl_mask & vk_mask))
        self.assertTrue(gl_mask[4, 4])
        self.assertTrue(vk_mask[4, 5])
        self.assertTrue(vk_mask[4, 6])
        self.assertEqual(int(gl_mask.sum()), 1)
        self.assertEqual(int(vk_mask.sum()), 2)
        with self.assertRaises(ValueError):
            mascaras_direcao_rgb(gl, vk[:, :, :2])

    def test_mapa_de_efeitos_sem_interpolacao(self):
        gl = np.zeros((64, 64), bool)
        vk = gl.copy()
        gl[3, 3] = True
        vk[3, 4] = True
        gl[8, 8] = vk[8, 8] = True
        arquivo = Path(self.tmp.name) / "mapa.png"
        rel = salvar_mapa_categorias(gl, vk, arquivo)
        self.assertEqual(len(rel["sha256_png"]), 64)
        self.assertTrue(arquivo.is_file())
        with self.assertRaises(ValueError):
            salvar_mapa_categorias(gl.astype(np.uint8), vk, arquivo)


if __name__ == "__main__":
    unittest.main()
