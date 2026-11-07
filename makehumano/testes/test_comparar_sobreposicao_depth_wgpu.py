"""Regressões CPU: profundidade, A2C e ordem de duas faces MSAA4×.

Os fixtures são gerados em RGB e PNG reais, independentes de Qt/GL/GPU.
Não presumem histogramas exatos em fronteiras de pixels.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato_sobreposicao_depth_sintetica import (
    CASOS_SOBREPOSICAO, criar_registro, resumir_rgb,
    sequencia_draw, vertices_com_profundidade,
)
from comparar_sobreposicao_depth_sintetica import (
    auditar_manifesto, comparar_sobreposicao, salvar_mapa,
)
from auditar_cobertura_a2c_sintetica import salvar_png_rgb


class TesteSobreposicaoDepth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gl = self._fixture("OpenGL")
        self.vk = self._fixture("Vulkan")

    def _imagem(self, a2c, escrita_z):
        rgb = np.zeros((64, 64, 3), np.uint8)
        rgb[:, :, 2] = 255
        if escrita_z:
            if a2c:
                rgb[14:50, 12:51] = (128, 0, 127)
                rgb[14, 12:51] = (64, 0, 191)
            else:
                rgb[14:50, 12:51] = (255, 0, 0)
                rgb[14, 12:51] = (128, 0, 127)
        return rgb

    def _fixture(self, backend):
        controles = {}
        for nome, a2c, escreve_z, ordem in CASOS_SOBREPOSICAO:
            img = self._imagem(a2c, escreve_z)
            arquivo = Path(self.tmp.name) / (backend + "-" + nome + ".png")
            c = criar_registro(
                img, arquivo, nome=nome, a2c=a2c,
                escrita_z=escreve_z, ordem=ordem,
                rastros=sequencia_draw(a2c, escreve_z, ordem),
            )
            if backend == "OpenGL":
                c.update({
                    "amostras_fbo_observadas": 4,
                    "fbo_depth_formato": "depth24",
                })
            else:
                c.update({
                    "formato_depth_pipeline": "depth24plus",
                    "amostras_depth_configuradas": 4,
                })
            controles[nome] = c
        return {
            "backend": backend,
            "tipo": "SOBREPOSICAO_DEPTH_A2C_SINTETICA",
            "nao_homologado": True,
            "controles": controles,
        }

    def alterar_png(self, doc, nome, rgb):
        c = doc["controles"][nome]
        arq = Path(self.tmp.name) / (
            doc["backend"] + "-alterado-" + nome + ".png"
        )
        c.update(resumir_rgb(rgb))
        c["png"] = str(arq)
        c["sha256_png"] = salvar_png_rgb(rgb, arq)

    def test_contratos_normais_de_z_e_ordem(self):
        out = comparar_sobreposicao(self.gl, self.vk)
        self.assertEqual(out["estado"], "VERIFICADO_SEM_HOMOLOGACAO")
        self.assertTrue(out["nao_homologado"])
        self.assertEqual(out["resultados"]["a2c_on_z_on"][
            "pixels_rgb_diferentes"], 0)
        self.assertEqual(out["resultados"]["a2c_on_z_off"][
            "centro_rgb_gl"], [0, 0, 255])
        self.assertEqual(out["resultados"]["a2c_on_z_on"][
            "centro_rgb_vk"], [128, 0, 127])
        self.assertEqual(out["resultados"]["a2c_off_z_on"][
            "centro_rgb_gl"], [255, 0, 0])

    def test_depth_convertido_com_mesmo_contrato_nos_backends(self):
        self.assertEqual(vertices_com_profundidade("frente")[0][2], 0.25)
        self.assertEqual(vertices_com_profundidade("fundo")[0][2], 0.75)
        self.assertEqual(
            [p["face"] for p in sequencia_draw(True, True, "fundo_primeiro")],
            ["fundo", "frente"],
        )
        with self.assertRaises(ValueError):
            vertices_com_profundidade("unknown")
        with self.assertRaises(ValueError):
            sequencia_draw(True, True, "other")

    def test_falha_sem_escrita_z_nao_pode_mostrar_vermelho(self):
        nome = "a2c_on_z_off"
        rgb = self._imagem(True, False)
        rgb[32, 32] = (128, 0, 127)
        self.alterar_png(self.gl, nome, rgb)
        with self.assertRaisesRegex(ValueError, "fundo deveria"):
            auditar_manifesto(self.gl, "OpenGL")

    def test_rejeita_ordem_inversa_com_resultado_diferente(self):
        nome = "a2c_on_z_on_inverso"
        rgb = self._imagem(True, True)
        rgb[32, 32] = (64, 0, 191)
        self.alterar_png(self.vk, nome, rgb)
        with self.assertRaisesRegex(ValueError, "Ordem/restauração"):
            auditar_manifesto(self.vk, "Vulkan")

    def test_rejeita_estado_gpu_incompatível(self):
        self.gl["controles"]["a2c_on_z_on"][
            "rastros_draw"
        ][0]["escrita_z"] = False
        with self.assertRaisesRegex(ValueError, "Estados do draw"):
            comparar_sobreposicao(self.gl, self.vk)

    def test_rejeita_fbo_sem_quatro_amostras(self):
        self.gl["controles"]["a2c_off_z_on"][
            "amostras_fbo_observadas"
        ] = 1
        with self.assertRaisesRegex(ValueError, "FBO OpenGL"):
            auditar_manifesto(self.gl, "OpenGL")

    def test_rejeita_hash_corrompido(self):
        self.vk["controles"]["a2c_off_z_on"]["sha256_png"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Hash PNG"):
            auditar_manifesto(self.vk, "Vulkan")

    def test_compara_delta_na_borda_sem_impor_zero(self):
        nome1 = "a2c_off_z_on"
        nome2 = "a2c_off_z_on_inverso"
        for nome in (nome1, nome2):
            rgb = self._imagem(False, True)
            rgb[14, 25] = (191, 0, 64)
            self.alterar_png(self.vk, nome, rgb)
        rel = comparar_sobreposicao(self.gl, self.vk)
        self.assertEqual(rel["resultados"][nome1]["pixels_rgb_diferentes"], 1)
        self.assertEqual(rel["resultados"][nome1][
            "pixels_divergentes_na_borda_msaa"], 1)
        self.assertEqual(rel["resultados"][nome1][
            "pixels_divergentes_fora_borda"], 0)

    def test_salva_mapa_diferenca_de_cor(self):
        a = self._imagem(True, True)
        b = a.copy()
        b[14, 20] = (191, 0, 64)
        resultado = salvar_mapa(
            a, b, Path(self.tmp.name) / "comparacao-depth.png"
        )
        self.assertEqual(resultado["ampliacao_sem_interpolacao"], 8)
        self.assertEqual(len(resultado["sha256_png"]), 64)
        self.assertTrue(Path(resultado["arquivo"]).is_file())


if __name__ == "__main__":
    unittest.main()
