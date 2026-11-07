"""Testes CPU do contrato GPU de triângulos coincidentes sob MSAA4×.

Fixtures RGB salvos em PNG; não assume qual backend faz pixel de borda
mais claro. Rejeita estados Z incorretos, desnível falso e deriva de ordem.
"""
import sys
import tempfile
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato_coplanares_depth_sintetica import (
    CASOS_COPLANARES, DEPTH_AZUL, DEPTH_SEPARACAO,
    centro_esperado, classificar_centro, passos_desenho,
    registrar_captura, vertices_face,
)
from comparar_coplanares_depth_sintetica import (
    comparar_coplanares, diferenca_rgb, ler_manifesto,
)


class TesteCoplanaresDepth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gl = self._criar("OpenGL")
        self.vk = self._criar("Vulkan")

    def _imagem(self, classe):
        img = np.zeros((64, 64, 3), np.uint8)
        if classe == "vermelho":
            cor = (255, 0, 0)
        elif classe == "azul":
            cor = (0, 0, 255)
        elif classe == "misto_a2c_4x":
            cor = (128, 0, 127)
        else:
            raise ValueError("Classe sintética inválida")
        img[13:53, 12:51] = cor
        if classe == "vermelho":
            img[13, 12:51] = (128, 0, 0)
        elif classe == "azul":
            img[13, 12:51] = (0, 0, 128)
        else:
            img[13, 12:51] = (64, 0, 64)
        return img

    def _criar(self, backend):
        controles = {}
        for caso in CASOS_COPLANARES:
            nome, comp, a2c, grava, ordem, distancia = caso
            classe = centro_esperado(comp, a2c, grava, ordem, distancia)
            img = self._imagem(classe)
            png = Path(self.tmp.name) / (backend + "-" + nome + ".png")
            controle = registrar_captura(
                img, png, caso, passos_desenho(comp, a2c, grava, ordem)
            )
            if backend == "OpenGL":
                controle.update({
                    "amostras_fbo_observadas": 4,
                    "formato_depth_fbo": "depth24",
                    "depth_range": [0.0, 1.0],
                })
            else:
                controle.update({
                    "formato_depth_pipeline": "depth24plus",
                    "amostras_depth_configuradas": 4,
                })
            controles[nome] = controle
        return {
            "backend": backend,
            "tipo": "COPLANARES_MSAA_Z_4X",
            "nao_homologado": True,
            "controles": controles,
        }

    def test_criterios_igualdade_e_desnivel(self):
        self.assertEqual(DEPTH_AZUL, 0.5)
        self.assertEqual(DEPTH_SEPARACAO, 2 ** -18)
        self.assertEqual(
            vertices_face("vermelho", DEPTH_SEPARACAO)[0][2],
            0.5 - DEPTH_SEPARACAO
        )
        self.assertEqual(
            centro_esperado("less", False, True, "azul_primeiro", 0.0),
            "azul"
        )
        self.assertEqual(
            centro_esperado("less-equal", False, True, "azul_primeiro", 0.0),
            "vermelho"
        )
        self.assertEqual(
            centro_esperado("less", False, True,
                            "azul_primeiro", DEPTH_SEPARACAO),
            "vermelho"
        )
        with self.assertRaises(ValueError):
            passos_desenho("always", False, True, "azul_primeiro")
        with self.assertRaises(ValueError):
            vertices_face("vermelho", 0.1)

    def test_contratos_validos_e_resultados_sem_impor_paridade(self):
        rel = comparar_coplanares(self.gl, self.vk)
        self.assertEqual(rel["estado"], "CONTROLES_GPU_REAIS_COM_CONTRATO_VERIFICADO")
        self.assertTrue(rel["nao_homologado"])
        self.assertEqual(
            rel["resultados_gl_vs_vulkan"][
                "igual_less_on_z_on_vermelho_primeiro"
            ]["pixels_rgb_diferentes"], 0
        )
        self.assertGreater(
            rel["contrastes_por_backend"]["gl"][
                "coplanar_vs_proximo_azul_primeiro"
            ]["pixels_rgb_diferentes"], 0
        )
        self.assertEqual(
            rel["contrastes_por_backend"]["vk"][
                "repeticao_com_a2c"
            ]["pixels_rgb_diferentes"], 0
        )

    def test_rejeita_funcao_depth_adulterada(self):
        nome = "igual_lequal_off_z_on_azul_primeiro"
        self.gl["controles"][nome]["rastros"][0]["depth_compare"] = "less"
        with self.assertRaisesRegex(ValueError, "Estados"):
            ler_manifesto(self.gl, "OpenGL")

    def test_rejeita_separacao_de_depth_falsa(self):
        nome = "perto_less_off_z_on_azul_primeiro"
        self.vk["controles"][nome]["separacao_depth"] = 0.0
        with self.assertRaisesRegex(ValueError, "Estados"):
            ler_manifesto(self.vk, "Vulkan")

    def test_rejeita_centro_errado_apesar_de_png_valido(self):
        nome = "igual_less_on_z_on_azul_primeiro"
        c = self.vk["controles"][nome]
        c["centro_classe"] = "misto_a2c_4x"
        with self.assertRaisesRegex(ValueError, "Centro/bytes"):
            ler_manifesto(self.vk, "Vulkan")

    def test_rejeita_png_corrompido(self):
        nome = "igual_less_off_z_on_vermelho_primeiro"
        self.gl["controles"][nome]["sha256_png"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "PNG coplanar"):
            ler_manifesto(self.gl, "OpenGL")

    def test_rejeita_repeticao_com_pixels_diferentes(self):
        nome = "igual_less_on_z_on_repeticao"
        c = self.gl["controles"][nome]
        rgb = self._imagem("misto_a2c_4x")
        rgb[13, 14] = (128, 0, 127)
        destino = Path(self.tmp.name) / "repeticao-alterada.png"
        # Regenera os hashes para provar que a comparação é de pixels,
        # não apenas de arquivos adulterados sem atualizar o manifesto.
        novo = registrar_captura(
            rgb, destino, CASOS_COPLANARES[-1],
            passos_desenho("less", True, True, "vermelho_primeiro")
        )
        c.update({
            k: novo[k] for k in (
                "centro_rgb", "centro_classe", "sha256_png",
                "sha256_rgb", "arquivo_png", "pixels_vermelho",
                "pixels_azul", "pixels_mistos",
            )
        })
        with self.assertRaisesRegex(ValueError, "Ordem ou repetição"):
            ler_manifesto(self.gl, "OpenGL")

    def test_relatorio_permite_diferenca_na_borda(self):
        nome = "igual_less_off_z_on_vermelho_primeiro"
        nome_repeticao = "igual_less_on_z_on_vermelho_primeiro"
        # A diferença real GL/VK é medida e publicada, não falsamente zerada.
        out = diferenca_rgb(
            self._imagem("vermelho"),
            self._imagem("misto_a2c_4x")
        )
        self.assertGreater(out["pixels_rgb_diferentes"], 0)

    def test_rejeita_fbo_sem_amostras(self):
        nome = "igual_less_off_z_on_vermelho_primeiro"
        self.gl["controles"][nome]["amostras_fbo_observadas"] = 1
        with self.assertRaisesRegex(ValueError, "GL FBO"):
            ler_manifesto(self.gl, "OpenGL")


if __name__ == "__main__":
    unittest.main()
