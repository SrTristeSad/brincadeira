"""Smoke GPU de GL_POINTS da GUI original, sem criar novo editor.

Executa a mesma CenaVulkan com um objeto auxiliar temporário. Os dados
da malha humana e a cena original não são modificados.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from vulkan_scene import matriz_wgpu


def validar_pontos(cena, cameras, mundo, arquivo):
    """Exige ponto visível no framebuffer Vulkan e contagem do draw."""
    corpo = next((
        obj for obj in mundo
        if obj.visibility and obj.cameraMode == 0
        and np.asarray(obj.primitives).ndim == 2
        and np.asarray(obj.primitives).shape[1] in (3, 4)
        and len(obj.verts) > 0
    ), None)
    if corpo is None:
        raise RuntimeError("Smoke de pontos: malha original ausente")

    from vulkan_displacement import posicoes_render
    coords = posicoes_render(corpo)
    from core import G
    mvp = matriz_wgpu(
        cameras[0], corpo, tamanho_origem=(G.windowWidth, G.windowHeight),
        tamanho_destino=(160, 120),
    )
    clip = np.column_stack((coords, np.ones(len(coords)))) @ mvp.T
    w = clip[:, 3]
    dentro = (
        (w > 1e-6)
        & (clip[:, 2] > 0) & (clip[:, 2] < w)
        & (np.abs(clip[:, 0]) < 0.4 * w)
        & (np.abs(clip[:, 1]) < 0.4 * w)
    )
    if not np.any(dentro):
        raise RuntimeError("Smoke de pontos: nenhum vértice no centro da câmera")
    candidatos = np.flatnonzero(dentro)
    distancias = np.sum((clip[candidatos, :2] / w[candidatos, None]) ** 2, axis=1)
    indice = int(candidatos[np.argmin(distancias)])

    class PontoOriginal:
        """Só troca a primitiva; o modelo/câmera continuam originais."""

        name = "smoke GL_POINTS"
        primitives = np.array([[indice]], dtype=np.uint32)
        material = SimpleNamespace(
            shader=None, opacity=1.0, transparent=False,
            shaderConfig={}, shaderParameters={},
            castShadows=False, receiveShadows=False,
        )
        depthless = True
        shadeless = True
        isTextured = False
        nTransparentPrimitives = 0

        def __init__(self, base):
            self.base = base
            self.color = np.full((len(base.verts), 4), 255, dtype=np.uint8)

        def __getattr__(self, key):
            return getattr(self.base, key)

    ponto = PontoOriginal(corpo)
    rgba = cena.capturar_framebuffer(
        [ponto], cameras, 160, 120, incluir_alfa=True,
        cor_fundo=(0.0, 0.0, 0.0, 0.0),
    )
    cobertura = int(np.count_nonzero(rgba[:, :, 3]))
    if cena.pontos_desenhados != 1 or cobertura < 1:
        raise RuntimeError(
            f"GL_POINTS Vulkan: desenho inválido (pontos={cena.pontos_desenhados}, "
            f"pixels={cobertura})"
        )
    Path(arquivo).write_text(
        json.dumps({"pontos": cena.pontos_desenhados, "pixels": cobertura})
        + "\n", encoding="utf-8",
    )
    print(f"MAKEHUMANO_VULKAN: GL_POINTS GPU OK pixels={cobertura}", flush=True)
