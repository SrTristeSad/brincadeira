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

from vulkan_capture import recortar_captura_rgb

from vulkan_scene import (
    CenaVulkan, preparar_malha_original, matriz_wgpu, assinatura_textura,
    parametros_material_vulkan,
)


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


class TestarInvalidacaoTexturasVulkan(unittest.TestCase):
    def setUp(self):
        # O metodo opera apenas no cache; nao precisa criar device GPU.
        self.cena = CenaVulkan.__new__(CenaVulkan)
        self.a = object()
        self.b = object()
        self.cena._texturas = {
            "pele.png": ((1, 5), self.a),
            "cabelo.png": ((2, 8), self.b),
        }

    def test_invalida_uma_textura_sem_afetar_outras(self):
        self.cena.invalidar_texturas("pele.png")
        self.assertNotIn("pele.png", self.cena._texturas)
        self.assertIs(self.cena._texturas["cabelo.png"][1], self.b)

    def test_invalida_todas_as_texturas(self):
        self.cena.invalidar_texturas()
        self.assertEqual(self.cena._texturas, {})

    def test_textura_nao_carregada_nao_provoca_erro(self):
        self.cena.invalidar_texturas("inexistente.png")
        self.assertEqual(len(self.cena._texturas), 2)


class TestarMaterialOriginalNoShaderVulkan(unittest.TestCase):
    def _obj(self, *, shadeless=False, diffuse=True, rgb=(0.2, 0.4, 0.8)):
        return SimpleNamespace(
            material=SimpleNamespace(
                diffuseColor=SimpleNamespace(values=rgb),
                shadeless=shadeless,
            ),
            shadeless=shadeless,
            isTextured=diffuse,
        )

    def test_material_padrao_mantem_luz_e_textura(self):
        cor, flags = parametros_material_vulkan(self._obj())
        np.testing.assert_allclose(cor, [0.2, 0.4, 0.8, 1.0])
        np.testing.assert_array_equal(flags, [0.0, 1.0, 0.0, 0.0])

    def test_shadeless_desliga_luz_sem_perder_a_textura(self):
        _, flags = parametros_material_vulkan(self._obj(shadeless=True))
        np.testing.assert_array_equal(flags[:2], [1.0, 1.0])

    def test_diffuse_desativada_ignora_amostragem_de_textura(self):
        _, flags = parametros_material_vulkan(self._obj(diffuse=False))
        np.testing.assert_array_equal(flags[:2], [0.0, 0.0])

    def test_rejeita_cor_difusa_nao_finita(self):
        with self.assertRaises(ValueError):
            parametros_material_vulkan(self._obj(rgb=(0.1, float("nan"), 1.0)))

    def test_material_nao_definido_usa_cor_branca(self):
        obj = SimpleNamespace()
        cor, flags = parametros_material_vulkan(obj)
        np.testing.assert_array_equal(cor, [1, 1, 1, 1])
        np.testing.assert_array_equal(flags[:2], [0, 1])


class TestarCapturaDaViewportOriginal(unittest.TestCase):
    def setUp(self):
        self.pixels = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)

    def test_recorte_interno_em_coordenadas_qt(self):
        recorte = recortar_captura_rgb(self.pixels, 1, 1, 3, 2)
        np.testing.assert_array_equal(recorte, self.pixels[1:3, 1:4])
        self.assertTrue(recorte.flags.c_contiguous)

    def test_captura_parcial_mantem_tamanho_e_cinza_externo(self):
        recorte = recortar_captura_rgb(self.pixels, -1, -1, 3, 3)
        self.assertEqual(recorte.shape, (3, 3, 3))
        self.assertTrue(np.all(recorte[0] == 127))
        self.assertTrue(np.all(recorte[:, 0] == 127))
        np.testing.assert_array_equal(recorte[1:, 1:], self.pixels[:2, :2])

    def test_captura_totalmente_fora_da_viewport(self):
        recorte = recortar_captura_rgb(self.pixels, 100, 100, 2, 2)
        self.assertEqual(recorte.shape, (2, 2, 3))
        self.assertTrue(np.all(recorte == 127))

    def test_valida_dimensoes_e_formato(self):
        with self.assertRaises(RuntimeError):
            recortar_captura_rgb(self.pixels, 0, 0, 0, 5)
        with self.assertRaises(ValueError):
            recortar_captura_rgb(self.pixels[:, :, :2], 0, 0, 1, 1)
        with self.assertRaises(ValueError):
            recortar_captura_rgb(self.pixels.astype(np.float32), 0, 0, 1, 1)


if __name__ == "__main__":
    unittest.main()
