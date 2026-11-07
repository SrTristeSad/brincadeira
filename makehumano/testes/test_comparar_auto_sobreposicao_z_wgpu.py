"""Testes CPU de integridade do mapa real Z × projeção da malha."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditar_auto_sobreposicao_malha import auditar_corpo, SEM_Z, COM_Z
from comparar_auto_sobreposicao_z import (
    auditar_registro, comparar_analises, gerar_mapa,
)
from auditar_cobertura_a2c_sintetica import salvar_png_rgb


class Camera:
    updated = True

    def getMatrices(self, _eye):
        return np.eye(4), np.eye(4)

    def getModelMatrix(self, _body):
        return np.eye(4)


class TesteIntegridadeAutoSobreposicao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = np.array([
            [-0.6, -0.6, 0.0], [0.6, -0.6, 0.0], [0.0, 0.6, 0.0],
        ], np.float32)
        corpo = SimpleNamespace(
            verts=np.vstack([base, base + [0, 0, 0.2]]),
            primitives=np.array([[0, 1, 2], [3, 4, 5]], np.uint32),
        )
        off = np.zeros((768, 1024, 3), np.uint8)
        off[260:510, 360:665] = 100
        on = off.copy()
        on[384, 512] = 220
        self.gl = self._fixture("OpenGL", corpo, off, on)
        self.vk = self._fixture("Vulkan", corpo, off, on)

    def _fixture(self, backend, corpo, off, on):
        doc = {
            "backend": backend,
            "controles": {},
            "auditoria_auto_sobreposicao_z": auditar_corpo(
                corpo, Camera(), off, on, max_controles=5
            ),
        }
        for nome, dados, z in (
            (SEM_Z, off, False), (COM_Z, on, True)
        ):
            caminho = Path(self.temp.name) / (
                backend + "-" + nome + ".png"
            )
            sha = salvar_png_rgb(dados, caminho)
            doc["controles"][nome] = {
                "arquivo_rgb": str(caminho),
                "sha256_png": sha,
                "sha256_rgb": doc["auditoria_auto_sobreposicao_z"][
                    "sha256_rgb_" + ("com_z" if z else "sem_z")
                ],
                "captura_rgb": True,
                "amostras": 4,
                "controle_blend_desligado": True,
                "pipeline_a2c_observado": False,
                "escrita_z_observada": z,
            }
        return doc

    def test_compara_candidatos_sem_confundir_visibilidade(self):
        rel, gl, vk = comparar_analises(self.gl, self.vk)
        self.assertTrue(rel["assinaturas_geometria_iguais"])
        self.assertTrue(rel["assinatura_mvp_igual"])
        self.assertEqual(rel["opengl"]["alterados"]["pixels"], 1)
        self.assertEqual(
            rel["opengl"]["alterados"]["com_pelo_menos_2_faces"], 1
        )
        self.assertEqual(rel["pixels_z_em_ambos"], 1)
        self.assertEqual(rel["pixels_z_uniao"], 1)
        self.assertTrue(rel["nao_homologado"])
        self.assertEqual(len(gl[0]["pixels_alterados"]["amostras_yx_faces"]), 1)
        self.assertEqual(int(gl[2].sum()), 1)

    def test_rejeita_hash_do_png_corrompido(self):
        self.gl["controles"][COM_Z]["sha256_png"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Hash PNG"):
            auditar_registro(self.gl, "OpenGL")

    def test_rejeita_incidencia_de_face_falsa(self):
        amostra = self.gl["auditoria_auto_sobreposicao_z"][
            "pixels_alterados"]["amostras_yx_faces"][0]
        amostra[2] = 0
        with self.assertRaisesRegex(ValueError, "Contagem"):
            auditar_registro(self.gl, "OpenGL")

    def test_rejeita_posicao_falsa_de_pixel_alterado(self):
        self.gl["auditoria_auto_sobreposicao_z"]["pixels_alterados"][
            "amostras_yx_faces"][0][0] += 1
        with self.assertRaisesRegex(ValueError, "Mapa de pixels"):
            auditar_registro(self.gl, "OpenGL")

    def test_rejeita_mascara_borda_sem_amostras_iguais(self):
        self.gl["controles"][SEM_Z]["amostras"] = 1
        with self.assertRaisesRegex(ValueError, "Estado RGB/Z"):
            auditar_registro(self.gl, "OpenGL")

    def test_gera_overlay_somente_nos_pixels_alterados(self):
        reg, rgb, mask = auditar_registro(self.vk, "Vulkan")
        out = gerar_mapa(
            reg, rgb, mask, Path(self.temp.name) / "overlay.png"
        )
        self.assertTrue(Path(out["png"]).is_file())
        self.assertEqual(len(out["sha256_png"]), 64)


if __name__ == "__main__":
    unittest.main()
