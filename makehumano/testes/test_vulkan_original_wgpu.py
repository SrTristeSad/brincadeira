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
from vulkan_offscreen import (
    bytes_por_linha_alinhados, decodificar_buffer_rgb,
    decodificar_buffer_rgba, mascarar_alfa_rgba,
)

from vulkan_scene import (
    CenaVulkan, preparar_malha_original, matriz_wgpu, assinatura_textura,
    parametros_material_vulkan, pixels_textura_rgba, aparencia_material_vulkan,
    configuracao_raster_vulkan, parametros_normalmap_vulkan,
    matriz_normal_vulkan,
)
from vulkan_texture import Texture as TextureVulkan
from vulkan_skin import preparar_skin, normalizar_cor_fundo
from vulkan_lighting import dados_iluminacao_cena
from vulkan_shader import configuracao_shader_nativo, nome_preset_nativo, PRESETS_NATIVOS


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


class TestarBufferOffscreenVulkan(unittest.TestCase):
    def test_stride_rgba_alinhado_a_256(self):
        self.assertEqual(bytes_por_linha_alinhados(1), 256)
        self.assertEqual(bytes_por_linha_alinhados(64), 256)
        self.assertEqual(bytes_por_linha_alinhados(65), 512)
        self.assertEqual(bytes_por_linha_alinhados(128), 512)

    def test_reconstroi_rgba_com_padding(self):
        dados = bytearray(256 * 2)
        dados[:8] = bytes([11, 22, 33, 255, 44, 55, 66, 255])
        dados[256:264] = bytes([77, 88, 99, 255, 10, 20, 30, 255])
        rgb = decodificar_buffer_rgb(dados, 2, 2, "rgba8unorm")
        self.assertEqual(rgb.shape, (2, 2, 3))
        np.testing.assert_array_equal(rgb[0, 0], [11, 22, 33])
        np.testing.assert_array_equal(rgb[1, 1], [10, 20, 30])
        self.assertTrue(rgb.flags.c_contiguous)

    def test_bgra_converte_canais_em_ordem_rgb(self):
        dados = bytearray(256)
        dados[:4] = bytes([33, 22, 11, 255])
        rgb = decodificar_buffer_rgb(dados, 1, 1, "bgra8unorm-srgb")
        np.testing.assert_array_equal(rgb[0, 0], [11, 22, 33])

    def test_rejeita_stride_tamanho_e_formato_invalidos(self):
        with self.assertRaises(ValueError):
            bytes_por_linha_alinhados(0)
        with self.assertRaises(ValueError):
            decodificar_buffer_rgb(bytes(12), 1, 1, "rgba8unorm")
        with self.assertRaises(ValueError):
            decodificar_buffer_rgb(bytes(256), 1, 1, "r8unorm")
        with self.assertRaises(ValueError):
            decodificar_buffer_rgb(bytes(256), 1, 0, "rgba8unorm")


class TestarProjecaoOffscreenVulkan(unittest.TestCase):
    def _camera(self, perspectiva=True):
        proj = np.eye(4, dtype=np.float32)
        proj[0, 0] = 1.5
        proj[1, 1] = 3.0
        if perspectiva:
            proj[2, 2] = -1.1
            proj[2, 3] = -0.2
            proj[3, 2] = -1.0
            proj[3, 3] = 0.0
        estado = dict(proj=proj.copy(), calls=0)
        identidade = np.eye(4, dtype=np.float32)
        def get_matrices(eye):
            estado["calls"] += 1
            return proj, identidade
        camera = SimpleNamespace(
            updated=True,
            getMatrices=get_matrices,
            getModelMatrix=lambda obj: identidade,
        )
        return camera, estado

    def test_muda_proporcao_perspectiva_sem_mutar_proj_original(self):
        camera, estado = self._camera(True)
        matrix = matriz_wgpu(
            camera, objeto_original(),
            tamanho_origem=(640, 480), tamanho_destino=(800, 400),
        )
        self.assertAlmostEqual(matrix[0, 0], 1.5 * (640/480) / (800/400))
        self.assertAlmostEqual(matrix[1, 1], 3.0)
        np.testing.assert_array_equal(estado["proj"], camera.getMatrices(0)[0])

    def test_muda_proporcao_ortografica_preservando_eixo_vertical(self):
        camera, _ = self._camera(False)
        matrix = matriz_wgpu(
            camera, objeto_original(),
            tamanho_origem=(640, 480), tamanho_destino=(400, 800),
        )
        self.assertAlmostEqual(matrix[0, 0], 1.5 * (640/480) / (400/800))
        self.assertAlmostEqual(matrix[1, 1], 3.0)

    def test_mesma_proporcao_nao_modifica_projecao(self):
        camera, _ = self._camera()
        original = matriz_wgpu(camera, objeto_original())
        diferente_resolucao = matriz_wgpu(
            camera, objeto_original(),
            tamanho_origem=(640, 480), tamanho_destino=(1280, 960),
        )
        np.testing.assert_allclose(original, diferente_resolucao)

    def test_rejeita_dimensoes_offscreen_invalidas(self):
        camera, _ = self._camera()
        with self.assertRaises(ValueError):
            matriz_wgpu(camera, objeto_original(),
                        tamanho_origem=(640, 480))
        with self.assertRaises(ValueError):
            matriz_wgpu(camera, objeto_original(),
                        tamanho_origem=(640, 480), tamanho_destino=(0, 480))


class TestarAlfaDeRenderizacaoVulkan(unittest.TestCase):
    def test_rgba_com_padding_preserva_alfa(self):
        raw = bytearray(256)
        raw[:8] = bytes((10, 20, 30, 0, 40, 50, 60, 200))
        rgba = decodificar_buffer_rgba(raw, 2, 1, "rgba8unorm")
        self.assertEqual(rgba.shape, (1, 2, 4))
        np.testing.assert_array_equal(rgba[0, 0], [10, 20, 30, 0])
        np.testing.assert_array_equal(rgba[0, 1], [40, 50, 60, 200])

    def test_bgra_preserva_alfa_na_conversao(self):
        raw = bytearray(256)
        raw[:4] = bytes((30, 20, 10, 155))
        rgba = decodificar_buffer_rgba(raw, 1, 1, "bgra8unorm-srgb")
        np.testing.assert_array_equal(rgba[0, 0], [10, 20, 30, 155])

    def test_mascara_conserva_cobertura_sem_cor(self):
        pixels = np.array([[[200, 25, 10, 0], [1, 2, 3, 128],
                            [255, 255, 255, 255]]], dtype=np.uint8)
        mascara = mascarar_alfa_rgba(pixels)
        self.assertEqual(mascara.shape, (1, 3, 3))
        np.testing.assert_array_equal(mascara[0, :, 0], [0, 128, 255])
        np.testing.assert_array_equal(mascara[0, :, 0], mascara[0, :, 1])
        np.testing.assert_array_equal(mascara[0, :, 0], mascara[0, :, 2])
        self.assertTrue(mascara.flags.c_contiguous)

    def test_mascara_rejeita_dados_invalidos(self):
        with self.assertRaises(ValueError):
            mascarar_alfa_rgba(np.zeros((1, 2, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            mascarar_alfa_rgba(np.zeros((1, 2, 4), dtype=np.float32))


class TestarTexturasSemOpenGL(unittest.TestCase):
    def test_cpu_texture_aloca_e_atualiza_subimagem(self):
        tex = TextureVulkan(size=(4, 3), components=3)
        self.assertEqual((tex.width, tex.height), (4, 3))
        self.assertEqual(tex.data.shape, (3, 4, 3))
        self.assertIsNone(tex.textureId)
        sub = SimpleNamespace(data=np.full((2, 2, 3), 97, np.uint8))
        tex.loadSubImage(sub, 1, 1)
        self.assertTrue(np.all(tex.data[1:3, 1:3] == 97))
        self.assertTrue(np.all(tex.data[0, :, :] == 0))

    def test_imagem_rgba_do_material_dinamico(self):
        cinza = pixels_textura_rgba(np.array([[[25]]], dtype=np.uint8))
        np.testing.assert_array_equal(cinza[0, 0], [25, 25, 25, 255])
        la = pixels_textura_rgba(np.array([[[30, 99]]], dtype=np.uint8))
        np.testing.assert_array_equal(la[0, 0], [30, 30, 30, 99])
        rgb = pixels_textura_rgba(np.array([[[1, 2, 3]]], dtype=np.uint8))
        np.testing.assert_array_equal(rgb[0, 0], [1, 2, 3, 255])

    def test_imagem_dinamica_rejeita_formatos_invalidos(self):
        with self.assertRaises(ValueError):
            pixels_textura_rgba(np.zeros((1, 1, 5), dtype=np.uint8))
        with self.assertRaises(ValueError):
            pixels_textura_rgba(np.zeros((1, 1, 4), dtype=np.float32))

    def test_subimagem_rejeita_fora_dos_limites(self):
        tex = TextureVulkan(size=(4, 4), components=4)
        sub = SimpleNamespace(data=np.zeros((3, 3, 4), dtype=np.uint8))
        with self.assertRaises(ValueError):
            tex.loadSubImage(sub, 2, 2)


class TestarRasterizacaoSkinVulkan(unittest.TestCase):
    def test_triangle_usa_cores_e_terceira_posicao_zero(self):
        pos = np.asarray([[0, 0], [1, 0], [0, 1]], np.float32)
        cores = np.array([[255, 0, 0, 255]] * 3, np.uint8)
        vertices, indices, linhas = preparar_skin(
            3, pos, index=np.array([[0, 1, 2]], np.uint32), color=cores,
        )
        self.assertEqual(vertices.shape, (3, 9))
        np.testing.assert_array_equal(vertices[:, 2], [0, 0, 0])
        np.testing.assert_array_equal(vertices[0, 5:], [1, 0, 0, 1])
        np.testing.assert_array_equal(indices, [0, 1, 2])
        self.assertFalse(linhas)

    def test_quad_cria_dois_triangulos_e_descarta_degenerados(self):
        pos = np.zeros((4, 2), dtype=np.float32)
        _, indices, _ = preparar_skin(
            4, pos, index=np.array([[0, 1, 2, 3], [0, 1, 1, 0]]),
        )
        np.testing.assert_array_equal(indices, [0, 1, 2, 0, 2, 3])

    def test_uv_linhas_mantem_indices(self):
        verts = np.zeros((4, 2), dtype=np.float32)
        _, indices, linhas = preparar_skin(
            2, verts, index=np.array([[0, 1], [1, 2], [2, 2]]),
        )
        np.testing.assert_array_equal(indices, [0, 1, 1, 2])
        self.assertTrue(linhas)

    def test_rejeita_faces_invalidas(self):
        verts = np.zeros((3, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            preparar_skin(3, verts, index=np.array([[0, 1, 9]]))
        with self.assertRaises(ValueError):
            preparar_skin(3, verts, UVs=np.zeros((3, 3)))
        with self.assertRaises(NotImplementedError):
            preparar_skin(5, verts)

    def test_normaliza_cores_rgba_legadas(self):
        self.assertEqual(
            normalizar_cor_fundo((0, 0, 0, 255)), (0., 0., 0., 1.),
        )
        self.assertEqual(
            normalizar_cor_fundo((0.5, 0.5, 0.5, 0.0)), (0.5, 0.5, 0.5, 0.0),
        )


class TestarLuzesOriginaisVulkan(unittest.TestCase):
    def _luz(self, posicao=(2, 3, 4), cor=(0.9, 0.8, 0.7)):
        return SimpleNamespace(
            position=posicao, color=SimpleNamespace(values=cor),
        )

    def test_mapeia_ambiente_e_luz_pontual_do_makehuman(self):
        cena = SimpleNamespace(
            environment=SimpleNamespace(
                ambience=SimpleNamespace(values=(0.2, 0.3, 0.4)),
            ),
            lights=[self._luz()],
        )
        ambiente, posicoes, cores, total = dados_iluminacao_cena(cena)
        self.assertEqual(total, 1)
        np.testing.assert_allclose(ambiente[:3], [0.2, 0.3, 0.4])
        np.testing.assert_allclose(posicoes[0], [2, 3, 4, 1])
        np.testing.assert_allclose(cores[0], [0.9, 0.8, 0.7, 1])
        self.assertEqual(posicoes.shape, (8, 4))
        self.assertEqual(cores.shape, (8, 4))
        self.assertEqual(posicoes.dtype, np.float32)

    def test_aceita_oito_luzes_sem_estourar_uniforms(self):
        cena = SimpleNamespace(
            environment=SimpleNamespace(ambience=(0.3, 0.3, 0.3)),
            lights=[self._luz() for _ in range(12)],
        )
        _, posicoes, cores, total = dados_iluminacao_cena(cena)
        self.assertEqual(total, 8)
        self.assertEqual(posicoes.shape, (8, 4))
        self.assertTrue(np.all(cores[:, 3] == 1))

    def test_cena_sem_luzes_mantem_ambiente(self):
        cena = SimpleNamespace(
            environment=SimpleNamespace(ambience=(0.5, 0.4, 0.3)),
            lights=[],
        )
        ambiente, posicoes, cores, total = dados_iluminacao_cena(cena)
        self.assertEqual(total, 0)
        np.testing.assert_array_equal(posicoes, np.zeros((8, 4)))
        np.testing.assert_array_equal(cores, np.zeros((8, 4)))
        np.testing.assert_allclose(ambiente[:3], [0.5, 0.4, 0.3])

    def test_rejeita_luz_com_posicao_invalida(self):
        cena = SimpleNamespace(
            environment=SimpleNamespace(ambience=(0.3, 0.3, 0.3)),
            lights=[self._luz(posicao=(float("nan"), 2, 3))],
        )
        with self.assertRaises(ValueError):
            dados_iluminacao_cena(cena)


class TestarAparenciaAvancadaDeMaterialVulkan(unittest.TestCase):
    def _obj(self, **atributos):
        padrao = {
            "specularColor": SimpleNamespace(values=(0.2, 0.4, 0.7)),
            "emissiveColor": SimpleNamespace(values=(0.05, 0.1, 0.2)),
            "shininess": 0.5,
            "opacity": 0.25,
        }
        padrao.update(atributos)
        return SimpleNamespace(material=SimpleNamespace(**padrao))

    def test_mapeia_specular_emissive_e_opacidade_originais(self):
        esp, ems, alfa = aparencia_material_vulkan(self._obj())
        np.testing.assert_allclose(esp, [0.2, 0.4, 0.7, 64.0])
        np.testing.assert_allclose(ems, [0.05, 0.1, 0.2, 0])
        self.assertAlmostEqual(alfa, 0.25)

    def test_opacidade_e_brilho_ficam_no_intervalo_original(self):
        esp, _, alfa = aparencia_material_vulkan(
            self._obj(shininess=9.0, opacity=-3.0),
        )
        self.assertEqual(esp[3], 128.0)
        self.assertEqual(alfa, 0.0)

    def test_sem_material_usa_opacidade_total_sem_especular(self):
        esp, ems, alfa = aparencia_material_vulkan(SimpleNamespace())
        np.testing.assert_array_equal(esp[:3], [0, 0, 0])
        np.testing.assert_array_equal(ems[:3], [0, 0, 0])
        self.assertAlmostEqual(alfa, 1.0)

    def test_rejeita_valores_nao_finitos(self):
        with self.assertRaises(ValueError):
            aparencia_material_vulkan(self._obj(opacity=float("nan")))
        with self.assertRaises(ValueError):
            aparencia_material_vulkan(self._obj(shininess=float("inf")))
        with self.assertRaises(ValueError):
            aparencia_material_vulkan(
                self._obj(specularColor=SimpleNamespace(values=(1, float("nan"), 0))),
            )


class TestarRegrasDeRasterOriginalVulkan(unittest.TestCase):
    def _obj(self, cull=0, depthless=False, opacity=1.0, transparent=False):
        return SimpleNamespace(
            cull=cull, depthless=depthless,
            material=SimpleNamespace(opacity=opacity, transparent=transparent),
        )

    def test_material_opaco_respeita_cull_back_e_z(self):
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(cull=1)),
            ("back", True, "less-equal"),
        )

    def test_cull_front_e_face_dupla(self):
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(cull=-1)),
            ("front", True, "less-equal"),
        )
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(cull=0)),
            ("none", True, "less-equal"),
        )

    def test_transparencia_nao_grava_z_mais_respeita_teste(self):
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(transparent=True)),
            ("none", False, "less-equal"),
        )
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(opacity=0.4)),
            ("none", False, "less-equal"),
        )

    def test_depthless_ignora_z_e_overlay_de_linhas_nao_grava(self):
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(depthless=True)),
            ("none", False, "always"),
        )
        self.assertEqual(
            configuracao_raster_vulkan(self._obj(), linhas=True),
            ("none", False, "less-equal"),
        )

    def test_opacidade_invalida_e_rejeitada(self):
        with self.assertRaises(ValueError):
            configuracao_raster_vulkan(self._obj(opacity=float("nan")))


class TestarNormalMapsOriginaisVulkan(unittest.TestCase):
    def _obj(self, caminho, **kwargs):
        material = dict(
            normalMapTexture=caminho, normalMapIntensity=0.65,
            shaderConfig={"normal": True},
        )
        material.update(kwargs)
        return SimpleNamespace(material=SimpleNamespace(**material))

    def test_habilita_textura_existente_e_preserva_intensidade(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "pele-normal.png"
            caminho.write_bytes(b"mock")
            caminho_out, intensidade = parametros_normalmap_vulkan(
                self._obj(str(caminho)),
            )
            self.assertEqual(caminho_out, str(caminho))
            self.assertAlmostEqual(intensidade, 0.65)

    def test_sem_textura_ou_config_desativada_nao_usa_normalmap(self):
        self.assertEqual(
            parametros_normalmap_vulkan(self._obj(None)), (None, 0.0),
        )
        self.assertEqual(
            parametros_normalmap_vulkan(self._obj("missing.png")),
            (None, 0.0),
        )
        self.assertEqual(
            parametros_normalmap_vulkan(
                self._obj("missing.png", shaderConfig={"normal": False}),
            ),
            (None, 0.0),
        )

    def test_limita_intensidade_ao_intervalo_do_material(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "normal.png"
            caminho.write_bytes(b"mock")
            self.assertEqual(
                parametros_normalmap_vulkan(
                    self._obj(str(caminho), normalMapIntensity=12.0),
                )[1], 1.0,
            )
            self.assertEqual(
                parametros_normalmap_vulkan(
                    self._obj(str(caminho), normalMapIntensity=-2.0),
                )[1], 0.0,
            )
            with self.assertRaises(ValueError):
                parametros_normalmap_vulkan(
                    self._obj(str(caminho), normalMapIntensity=float("nan")),
                )


class TestarMatrizNormalOriginalVulkan(unittest.TestCase):
    def test_escala_nao_uniforme_usa_inversa_transposta(self):
        modelo = np.diag([2.0, 4.0, 0.5, 1.0]).astype(np.float32)
        normal = matriz_normal_vulkan(modelo)
        np.testing.assert_allclose(normal.diagonal(), [0.5, 0.25, 2.0, 1.0])
        np.testing.assert_array_equal(modelo.diagonal(), [2, 4, 0.5, 1])

    def test_translacao_nao_muda_normal(self):
        modelo = np.eye(4, dtype=np.float32)
        modelo[:3, 3] = [2, 3, -9]
        np.testing.assert_allclose(
            matriz_normal_vulkan(modelo), np.eye(4, dtype=np.float32),
        )

    def test_matriz_degenerada_ou_nao_finita_e_rejeitada(self):
        modelo = np.eye(4, dtype=np.float32)
        modelo[2, 2] = 0
        with self.assertRaises(ValueError):
            matriz_normal_vulkan(modelo)
        modelo[2, 2] = float("nan")
        with self.assertRaises(ValueError):
            matriz_normal_vulkan(modelo)


class TestarPresetXrayOriginalVulkan(unittest.TestCase):
    def _material(self, **dados):
        valores = dict(
            shader="/data/shaders/glsl/xray",
            ambientColor=SimpleNamespace(values=(0.1, 0.2, 0.3)),
            shaderParameters={},
            shaderConfig={"diffuse": False, "vertexColors": False},
        )
        valores.update(dados)
        return SimpleNamespace(**valores)

    def test_material_xray_original_e_reconhecido(self):
        arquivo = (
            RAIZ / "codigo" / "makehuman" / "data" / "materials" / "xray.mhmat"
        )
        self.assertIn("shader data/shaders/glsl/xray", arquivo.read_text())
        modo, params, pendente = configuracao_shader_nativo(self._material())
        self.assertEqual(modo, 1)
        self.assertIsNone(pendente)
        np.testing.assert_allclose(params, [0.2, 1.0, 0.7, 0.0])

    def test_shader_xray_parametros_do_mhmat(self):
        material = self._material(
            shaderParameters={"edgefalloff": "3.5", "intensity": ["0.4"]},
            shaderConfig={"vertexColors": True},
        )
        modo, params, _ = configuracao_shader_nativo(material)
        self.assertEqual(modo, 1)
        np.testing.assert_allclose(params, [0.2, 3.5, 0.4, 1.0])

    def test_outros_shaders_glsl_nao_sao_marcados_como_portados(self):
        for nome in ("litsphere", "phong", "toon", "normalmap", "skin"):
            with self.subTest(shader=nome):
                modo, _, pendente = configuracao_shader_nativo(
                    self._material(shader="/data/shaders/glsl/" + nome)
                )
                self.assertEqual(modo, 0)
                self.assertEqual(pendente, nome)
        modo, _, pendente = configuracao_shader_nativo(
            self._material(shader="/outra-pasta/xray")
        )
        self.assertEqual(modo, 0)
        self.assertIsNotNone(pendente)

    def test_seletor_so_oferece_preset_portado(self):
        self.assertEqual(PRESETS_NATIVOS, frozenset(("xray",)))
        self.assertEqual(
            nome_preset_nativo("/data/shaders/glsl/xray"), "xray",
        )
        self.assertIsNone(
            nome_preset_nativo("/data/shaders/glsl/litsphere")
        )
        self.assertIsNone(nome_preset_nativo("/custom/xray"))

    def test_parametro_invalido_nao_e_aceito_pelo_renderer(self):
        with self.assertRaises(ValueError):
            configuracao_shader_nativo(
                self._material(shaderParameters={"edgefalloff": "nan"})
            )
        with self.assertRaises(ValueError):
            configuracao_shader_nativo(
                self._material(ambientColor=SimpleNamespace(
                    values=(1, float("nan"), 0)
                ))
            )


if __name__ == "__main__":
    unittest.main()
