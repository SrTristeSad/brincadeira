"""CPU-only tests for PNG integrity and the 4x A2C synthetic contract."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditar_cobertura_a2c_sintetica import (
    CASOS, DESLOCAMENTOS_SUBPIXEL, deslocamento_do_caso,
    geometria_do_caso, registrar_rgb, salvar_png_rgb, vertices_do_caso,
)
from comparar_a2c_sintetico_gpu import comparar_sintetico, mapa_diferenca_rgb


class TesteSinteticoGPU(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gl, self.vk = self.montar()

    def montar(self):
        controles = {}
        for nome, amostras, a2c, alfa in CASOS:
            valor = (
                255 if not a2c or alfa == 255 else
                0 if alfa == 0 else
                64 if alfa == 64 else
                128 if alfa == 128 else 192
            )
            if nome.startswith("aresta_"):
                cobertura = np.zeros((64, 64), np.uint8)
                cobertura[11:53, 12:53] = 255
                if amostras == 4:
                    cobertura[11, 12:53] = 128
                    cobertura[11:53, 12] = 128
                if not a2c:
                    canal = cobertura
                else:
                    canal = np.rint(
                        cobertura.astype(np.float64) * alfa / 255
                    ).astype(np.uint8)
                imagem = np.repeat(canal[:, :, None], 3, axis=2)
            else:
                imagem = np.full((64, 64, 3), valor, np.uint8)
            png = Path(self.tmp.name) / (nome + ".png")
            metrica = registrar_rgb(imagem)
            controles[nome] = {
                **metrica,
                "alfa_u8": alfa, "amostras": amostras,
                "amostras_fbo_observadas": amostras if amostras == 4 else 0,
                "a2c_ativo": a2c, "blend_ativo": False,
                "profundidade_ativa": False,
                "geometria": geometria_do_caso(nome),
                "vertices_ndc": [list(pt) for pt in vertices_do_caso(nome)],
                "deslocamento_px_ndc": list(deslocamento_do_caso(nome)),
                "png": str(png),
                "sha256_png": salvar_png_rgb(imagem, png),
            }
        modelo = {
            "tipo": "A2C_SINTETICO_UMA_SUPERFICIE",
            "controles": controles,
            "nao_homologado": True,
        }
        return (
            dict(copy.deepcopy(modelo), backend="OpenGL"),
            dict(copy.deepcopy(modelo), backend="Vulkan"),
        )

    def test_pareamento_valido_sem_forcar_histograma_exato(self):
        rel = comparar_sintetico(self.gl, self.vk)
        self.assertEqual(rel["estado"], "MEDIDO_SEM_HOMOLOGACAO")
        self.assertTrue(rel["nao_homologado"])
        self.assertEqual(
            rel["resultados"]["4x_a128_a2c_on"]["pixels_rgb_distintos"], 0
        )

    def test_aresta_real_identica_em_dois_backends(self):
        resultado = comparar_sintetico(self.gl, self.vk)
        self.assertEqual(
            resultado["resultados"]["aresta_4x_a128_a2c_on"][
                "pixels_rgb_distintos"
            ], 0,
        )
        self.assertGreater(
            resultado["analise_aresta"]["pixels_borda_parcial_gl"], 0,
        )
        self.assertEqual(resultado["analise_aresta"]["iou_efeito_a2c"], 1.0)

    def test_rejeita_vertices_distintos_na_aresta(self):
        self.vk["controles"]["aresta_4x_a128_a2c_on"][
            "vertices_ndc"
        ][0][0] += 0.1
        with self.assertRaisesRegex(ValueError, "Estados sintéticos"):
            comparar_sintetico(self.gl, self.vk)

    def test_rejeita_aresta_sem_cobertura_parcial(self):
        nome = "aresta_4x_a255_a2c_off"
        rgb = np.zeros((64, 64, 3), np.uint8)
        rgb[11:53, 12:53] = 255
        caminho = Path(self.tmp.name) / "sem-parcial.png"
        doc = self.vk["controles"][nome]
        doc.update(registrar_rgb(rgb))
        doc["png"] = str(caminho)
        doc["sha256_png"] = salvar_png_rgb(rgb, caminho)
        with self.assertRaisesRegex(ValueError, "cobertura parcial"):
            comparar_sintetico(self.gl, self.vk)

    def test_mapa_visual_distingue_mais_luminoso_gl_e_vk(self):
        gl = np.zeros((64, 64, 3), dtype=np.uint8)
        vk = gl.copy()
        gl[1, 1], vk[1, 1] = (64, 64, 64), (128, 128, 128)
        gl[1, 2], vk[1, 2] = (128, 128, 128), (64, 64, 64)
        gl[1, 3], vk[1, 3] = (255, 255, 255), (255, 255, 255)
        mapa = mapa_diferenca_rgb(gl, vk)
        self.assertEqual(mapa[1, 1].tolist(), [25, 220, 255])
        self.assertEqual(mapa[1, 2].tolist(), [255, 65, 65])
        self.assertEqual(mapa[1, 3].tolist(), [130, 130, 130])
        self.assertEqual(mapa[0, 0].tolist(), [0, 0, 0])
        with self.assertRaises(ValueError):
            mapa_diferenca_rgb(gl, vk[:, :, :2])

    def test_deslocamentos_iguais_e_quarto_de_pixel_ndc(self):
        nome = "aresta_dx_p025_4x_a255_a2c_off"
        original = vertices_do_caso("aresta_4x_a255_a2c_off")
        deslocado = vertices_do_caso(nome)
        self.assertEqual(len(DESLOCAMENTOS_SUBPIXEL), 4)
        self.assertAlmostEqual(deslocado[0][0] - original[0][0], 0.25 * 2 / 64)
        self.assertEqual(deslocado[0][1], original[0][1])
        self.assertEqual(deslocamento_do_caso(nome), (0.25, 0.0))
        self.assertEqual(deslocamento_do_caso("aresta_4x_a128_a2c_on"), (0.0, 0.0))
        self.assertEqual(len(CASOS), 22)

    def test_relatorio_aceita_diferencas_dependentes_do_deslocamento(self):
        nome = "aresta_dx_p025_4x_a255_a2c_off"
        c = self.vk["controles"][nome]
        from PIL import Image
        with Image.open(c["png"]) as imagem:
            rgb = np.asarray(imagem).copy()
        rgb[11, 20] = (191, 191, 191)
        arquivo = Path(self.tmp.name) / "alteracao-subpixel.png"
        c.update(registrar_rgb(rgb))
        c["png"] = str(arquivo)
        c["sha256_png"] = salvar_png_rgb(rgb, arquivo)
        rel = comparar_sintetico(self.gl, self.vk)["varredura_subpixel"]
        self.assertEqual(rel["estado"], "MEDIDO_SEM_HOMOLOGACAO")
        self.assertEqual(set(rel["posicoes"]), {
            "origem", "dx_m025", "dx_p025", "dy_m025", "dy_p025"
        })
        self.assertEqual(rel["posicoes"]["dx_p025"]["msaa_puro"][
            "pixels_diferentes"
        ], 1)
        self.assertEqual(rel["posicoes"]["origem"]["msaa_puro"][
            "pixels_diferentes"
        ], 0)
        self.assertEqual(rel["posicoes"]["dx_p025"]["msaa_puro"][
            "pixels_diferentes_na_borda_subpixel"
        ], 1)

    def test_rejeita_metadados_deslocamento_incorretos(self):
        nome = "aresta_dy_m025_4x_a128_a2c_on"
        self.vk["controles"][nome]["deslocamento_px_ndc"] = [0.0, 0.25]
        with self.assertRaisesRegex(ValueError, "Estados sintéticos"):
            comparar_sintetico(self.gl, self.vk)

    def test_rejeita_amostras_fbo_gl_falsas(self):
        self.gl["controles"]["4x_a128_a2c_on"]["amostras_fbo_observadas"] = 0
        with self.assertRaisesRegex(ValueError, "FBO"):
            comparar_sintetico(self.gl, self.vk)

    def test_rejeita_hash_png_corrompido(self):
        self.vk["controles"]["4x_a192_a2c_on"]["sha256_png"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Hash PNG"):
            comparar_sintetico(self.gl, self.vk)

    def test_rejeita_histograma_incoerente(self):
        self.gl["controles"]["4x_a064_a2c_on"]["media_r"] = 1
        with self.assertRaisesRegex(ValueError, "Histograma"):
            comparar_sintetico(self.gl, self.vk)

    def test_rejeita_borda_ou_canal_desigual(self):
        rgb = np.zeros((64, 64, 3), np.uint8)
        rgb[0, 0, 1] = 64
        with self.assertRaisesRegex(ValueError, "R=G=B"):
            registrar_rgb(rgb)
        with self.assertRaises(ValueError):
            salvar_png_rgb(np.zeros((4, 4, 3), np.uint8),
                           Path(self.tmp.name) / "bad.png")

    def test_rejeita_alpha_zero_sem_zerar_cobertura(self):
        imagem = np.ones((64, 64, 3), np.uint8)
        nome = "4x_a000_a2c_on"
        arquivo = Path(self.tmp.name) / "err-alpha.png"
        c = self.gl["controles"][nome]
        c.update(registrar_rgb(imagem))
        c["png"] = str(arquivo)
        c["sha256_png"] = salvar_png_rgb(imagem, arquivo)
        with self.assertRaisesRegex(ValueError, "alpha zero"):
            comparar_sintetico(self.gl, self.vk)


if __name__ == "__main__":
    unittest.main()
