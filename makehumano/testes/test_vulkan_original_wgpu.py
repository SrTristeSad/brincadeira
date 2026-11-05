"""Ponte de malhas e câmeras da GUI MakeHuman ORIGINAL para Vulkan.

Testes CPU usam a mesma interface que lib/object3d.Object3D fornece,
sem criar um editor paralelo nem importar o motor OpenGL.
"""
from pathlib import Path
import os
import tempfile
import sys
import unittest
from types import SimpleNamespace

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))

from vulkan_scene import preparar_malha_original, matriz_wgpu, assinatura_textura


def objeto_original(face=None):
    return SimpleNamespace(
        verts=np.asarray([
            [0, 0, 0], [1, 0, 0], [1, 1, 0],
            [0, 1, 0], [0, 0, 0],
        ], dtype=np.float32),
        norms=np.tile([0, 0, 1], (5, 1)),
        UVs=np.asarray([
            [0, 0], [1, 0], [1, 1], [0, 1], [0.8, 0.8]
        ], np.float32),
        hasUVs=True,
        color=np.asarray([[255, 128, 0, 255]] * 5, np.uint8),
        primitives=np.asarray(
            face if face is not None else [[0, 1, 2, 3]],
            dtype=np.uint32,
        ),
    )


class TestarMalhasDaGuiOriginal(unittest.TestCase):
    def test_quad_e_uvs_ja_desenroladas_vem_do_object3d(self):
        vertices, indices = preparar_malha_original(objeto_original())
        self.assertEqual(vertices.shape, (5, 12))
        self.assertEqual(vertices.dtype, np.float32)
        self.assertEqual(indices.tolist(), [0, 1, 2, 0, 2, 3])
        np.testing.assert_array_equal(
            vertices[:, 6:8],
            objeto_original().UVs,
        )
        np.testing.assert_allclose(
            vertices[:, 8:12][0], [1.0, 128 / 255, 0, 1.0],
        )

    def test_malha_original_sem_faces_pode_ser_auxiliar(self):
        origem = objeto_original()
        origem.primitives = np.array([], dtype=np.uint32)
        vertices, indices = preparar_malha_original(origem)
        self.assertEqual(vertices.shape, (5, 12))
        self.assertEqual(indices.shape, (0,))

    def test_grade_original_usa_segmentos_de_linha(self):
        origem = objeto_original([[0, 1], [1, 2], [2, 3], [3, 3]])
        vertices, indices = preparar_malha_original(origem)
        self.assertEqual(vertices.shape, (5, 12))
        self.assertEqual(indices.tolist(), [0, 1, 1, 2, 2, 3])

    def test_quads_degenerados_do_original_sao_triangulos(self):
        origem = objeto_original([[0, 1, 2, 0]])
        _, indices = preparar_malha_original(origem)
        self.assertEqual(indices.tolist(), [0, 1, 2])

    def test_indices_ja_filtrados_pelo_face_mask_original(self):
        origem = objeto_original([[0, 1, 2, 3], [0, 2, 3, 4]])
        _, full = preparar_malha_original(origem)
        self.assertEqual(len(full), 12)
        # module3d já passa apenas os índices da máscara em .primitives
        origem.primitives = origem.primitives[1:]
        _, filtrados = preparar_malha_original(origem)
        self.assertEqual(filtrados.tolist(), [0, 2, 3, 0, 3, 4])

    def test_morphs_deformam_os_vertices_originais_e_nao_uv(self):
        origem = objeto_original()
        antes, _ = preparar_malha_original(origem)
        origem.verts[1, 2] = 0.25
        depois, _ = preparar_malha_original(origem)
        self.assertAlmostEqual(depois[1, 2] - antes[1, 2], 0.25)
        np.testing.assert_array_equal(
            depois[:, 6:8], antes[:, 6:8],
        )

    def test_sem_uvs_tem_preenchimento_neutro(self):
        origem = objeto_original()
        origem.hasUVs = False
        origem.UVs = None
        vertices, _ = preparar_malha_original(origem)
        self.assertTrue(np.all(vertices[:, 6:8] == 0))

    def test_rejeita_indices_e_posicoes_invalidos(self):
        origem = objeto_original([[0, 1, 99, 3]])
        with self.assertRaises(ValueError):
            preparar_malha_original(origem)
        origem = objeto_original()
        origem.verts[0, 0] = np.nan
        with self.assertRaises(ValueError):
            preparar_malha_original(origem)

    def test_matriz_projecao_gl_para_depth_vulkan(self):
        identity = np.eye(4, dtype=np.float32)
        cam = SimpleNamespace(
            updated=False,
            updateCamera=lambda: None,
            getMatrices=lambda eye: (identity, identity),
            getModelMatrix=lambda obj: identity,
        )
        resultado = matriz_wgpu(cam, objeto_original())
        self.assertTrue(cam.updated)
        perto = resultado @ np.array([0, 0, -1, 1], np.float32)
        longe = resultado @ np.array([0, 0, 1, 1], np.float32)
        self.assertAlmostEqual(perto[2], 0)
        self.assertAlmostEqual(longe[2], 1)

    def test_conserva_modelo_original_da_camera(self):
        identidade = np.eye(4, dtype=np.float32)
        modelo = identidade.copy()
        modelo[0, 3] = 2
        cam = SimpleNamespace(
            updated=True,
            getMatrices=lambda eye: (identidade, identidade),
            getModelMatrix=lambda obj: modelo,
        )
        matriz = matriz_wgpu(cam, objeto_original())
        np.testing.assert_allclose(matriz[0, :], modelo[0, :])


class TestarAssinaturaTexturaVulkan(unittest.TestCase):
    def test_sem_arquivo_ou_caminho_usa_fallback(self):
        self.assertIsNone(assinatura_textura(None))
        self.assertIsNone(assinatura_textura(""))
        with tempfile.TemporaryDirectory() as pasta:
            self.assertIsNone(assinatura_textura(Path(pasta) / "ausente.png"))

    def test_detecta_modificacao_mesmo_com_tamanho_igual(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "textura.png"
            caminho.write_bytes(b"abcd")
            antes = assinatura_textura(caminho)
            info = caminho.stat()
            caminho.write_bytes(b"efgh")
            os.utime(caminho, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
            depois = assinatura_textura(caminho)
            self.assertNotEqual(antes, depois)
            self.assertEqual(antes[1], depois[1])

    def test_detecta_remocao_e_recriacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "textura.png"
            caminho.write_bytes(b"original")
            antes = assinatura_textura(caminho)
            caminho.unlink()
            self.assertIsNone(assinatura_textura(caminho))
            caminho.write_bytes(b"nova")
            self.assertNotEqual(antes, assinatura_textura(caminho))


if __name__ == "__main__":
    unittest.main()
