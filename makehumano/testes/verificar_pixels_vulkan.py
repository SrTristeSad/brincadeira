#!/usr/bin/env python3
"""Teste real de pixels da cena Vulkan da GUI ORIGINAL do MakeHuman.

Usa a própria CenaVulkan, objetos com os atributos públicos de Object3D
e rendercanvas.offscreen, sem interface alternativa ou shaders de teste.
Executar no CI com Vulkan/Lavapipe e wgpu instalados:

    WGPU_BACKEND_TYPE=Vulkan python -m unittest \
        makehumano/testes/verificar_pixels_vulkan.py -v

Não substitui a comparação visual humana da aplicação completa.
"""

import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))


def malha_original_simulada(nome, cor, z, *, opacidade=1.0,
                           transparentes=0, prioridade=0):
    """Object3D mínimo para exercitar o pipeline real, não um novo motor."""
    vertices = np.array([
        [-0.85, -0.85, z],
        [0.85, -0.85, z],
        [0.00, 0.85, z],
    ], dtype=np.float32)
    return SimpleNamespace(
        name=nome,
        priority=prioridade,
        visibility=True,
        verts=vertices,
        norms=np.tile(np.array([0, 0, 1], dtype=np.float32), (3, 1)),
        hasUVs=False,
        color=np.full((3, 4), 255, dtype=np.uint8),
        primitives=np.array([[0, 1, 2]], dtype=np.uint32),
        cameraMode=0,
        solid=True,
        shadeless=True,
        isTextured=False,
        texture=None,
        nTransparentPrimitives=transparentes,
        material=SimpleNamespace(
            diffuseColor=SimpleNamespace(values=tuple(cor)),
            opacity=opacidade,
        ),
    )


class TestarPixelsVulkanMakeHumanOriginal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # O teste não deve aceitar fallback para backend OpenGL.
        os.environ["WGPU_BACKEND_TYPE"] = "Vulkan"
        from rendercanvas.offscreen import RenderCanvas
        from vulkan_scene import CenaVulkan

        cls.canvas = RenderCanvas(size=(64, 64), pixel_ratio=1)
        cls.cena = CenaVulkan(cls.canvas)
        identidade = np.eye(4, dtype=np.float32)
        cls.camera = SimpleNamespace(
            updated=True,
            getMatrices=lambda olho: (identidade, identidade),
            getModelMatrix=lambda obj: identidade,
        )
        print("Pixels Vulkan original: adaptador =", cls.cena.adapter.info,
              "formato =", cls.cena.formato, flush=True)

    def desenhar_pixel(self, objetos, fundo=(0.0, 0.0, 0.0, 1.0)):
        self.canvas.request_draw(
            lambda: self.cena.desenhar(objetos, [self.camera], cor_fundo=fundo)
        )
        imagem = np.asarray(self.canvas.draw())
        self.assertEqual(imagem.shape, (64, 64, 4))
        self.assertGreater(self.cena.objetos_desenhados, 0)
        pixel = imagem[32, 32].astype(np.float32) / 255.0
        print("Pixel Vulkan:", pixel, flush=True)
        return pixel

    def conferir_rgb(self, pixel, esperado):
        esperado = np.array(esperado, dtype=np.float32)
        if "srgb" in str(self.cena.formato).lower():
            esperado = np.where(
                esperado <= 0.0031308,
                esperado * 12.92,
                1.055 * esperado ** (1.0 / 2.4) - 0.055,
            )
        np.testing.assert_allclose(pixel[:3], esperado, atol=0.045)

    def test_blend_alfa_meio_sobre_superficie_opaca(self):
        # Vermelho opaco atrás do verde semitransparente.
        # As cores são definidas pelo material original, sem textura.
        mundo = [
            malha_original_simulada("corpo", (1, 0, 0), 0.5, prioridade=0),
            malha_original_simulada(
                "roupa", (0, 1, 0), -0.5,
                opacidade=0.5, transparentes=1, prioridade=1,
            ),
        ]
        pixel = self.desenhar_pixel(mundo)
        self.conferir_rgb(pixel, (0.5, 0.5, 0.0))

    def test_depth_rejeita_transparente_oculto_por_opaco(self):
        # A transparência não deve aparecer através do corpo mais próximo.
        mundo = [
            malha_original_simulada("corpo", (1, 0, 0), -0.5, prioridade=0),
            malha_original_simulada(
                "roupa_oculta", (0, 1, 0), 0.5,
                opacidade=0.5, transparentes=1, prioridade=1,
            ),
        ]
        pixel = self.desenhar_pixel(mundo)
        self.conferir_rgb(pixel, (1.0, 0.0, 0.0))

    def test_transparente_nao_bloqueia_depth_de_desenho_posterior(self):
        # A ordem original de G.world é preservada. O teste confirma que
        # uma camada transparente não escreve profundidade indevidamente.
        mundo = [
            malha_original_simulada(
                "roupa_na_frente", (0, 1, 0), -0.5,
                opacidade=0.5, transparentes=1, prioridade=0,
            ),
            malha_original_simulada(
                "corpo_desenhado_depois", (1, 0, 0), 0.5, prioridade=1,
            ),
        ]
        pixel = self.desenhar_pixel(mundo)
        self.conferir_rgb(pixel, (1.0, 0.0, 0.0))

    def test_alfa_zero_preserva_o_pixel_original(self):
        mundo = [
            malha_original_simulada("corpo", (1, 0, 0), 0.5, prioridade=0),
            malha_original_simulada(
                "invisivel", (0, 1, 0), -0.5,
                opacidade=0.0, transparentes=1, prioridade=1,
            ),
        ]
        pixel = self.desenhar_pixel(mundo)
        self.conferir_rgb(pixel, (1.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
