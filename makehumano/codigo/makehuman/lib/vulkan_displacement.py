"""Displacement de vértices compartilhado por renderização e picking.

Não altera os arrays editáveis do MakeHuman nem aplica novos morph targets.
Altura preta é zero; branca desloca uma unidade local vezes a intensidade.
"""
import os
import numpy as np
from vulkan_material_maps import parametros_mapa


def _pixels(recurso):
    if isinstance(recurso, (str, os.PathLike)):
        # Mesmo cache CPU usado pela pintura/projeção original. Atualizações
        # em memória e recarga de arquivo devem mover render e picking juntos.
        from vulkan_texture import getTexture
        texture = getTexture(recurso)
        if texture is None:
            raise ValueError("Displacement: textura não disponível")
        return texture.data
    if isinstance(recurso, np.ndarray):
        return recurso
    from image import Image
    if isinstance(recurso, Image):
        from vulkan_texture import getTexture
        return getTexture(recurso).data
    return np.asarray(getattr(recurso, "data", None))


def amostrar_altura(pixels, uvs):
    """Filtro bilinear, clamp-to-edge e origem superior das imagens Qt."""
    pixels = np.asarray(pixels)
    uvs = np.asarray(uvs, dtype=np.float32)
    if (pixels.dtype != np.uint8 or pixels.ndim != 3
            or min(pixels.shape[:2]) < 1 or pixels.shape[2] not in (1, 2, 3, 4)):
        raise ValueError("Displacement exige imagem uint8 L, LA, RGB ou RGBA")
    if uvs.ndim != 2 or uvs.shape[1] != 2 or not np.isfinite(uvs).all():
        raise ValueError("Displacement exige UVs finitas Nx2")
    h, w = pixels.shape[:2]
    xy = np.clip(uvs, 0., 1.) * [w, -h] + [-.5, h-.5]
    lower = np.floor(xy).astype(np.intp)
    fraction = xy-lower
    x0, y0 = np.clip(lower, [0, 0], [w-1, h-1]).T
    x1, y1 = np.clip(lower+1, [0, 0], [w-1, h-1]).T

    def height(x, y):
        samples = pixels[y, x].astype(np.float32)
        return (samples[:, :1] if pixels.shape[2] < 3 else samples[:, :3]).mean(axis=1)/255.

    a = height(x0, y0)*(1.-fraction[:, 0]) + height(x1, y0)*fraction[:, 0]
    b = height(x0, y1)*(1.-fraction[:, 0]) + height(x1, y1)*fraction[:, 0]
    return np.asarray(a*(1.-fraction[:, 1])+b*fraction[:, 1], dtype=np.float32)


def posicoes_render(obj):
    positions = np.asarray(obj.verts, dtype=np.float32)
    resource, strength = parametros_mapa(getattr(obj, "material", None), "displacement")
    if resource is None:
        return positions
    if not bool(getattr(obj, "hasUVs", False)):
        raise ValueError("Displacement ativo exige UVs da malha original")
    normals = np.asarray(obj.norms, dtype=np.float32)
    uvs = np.asarray(obj.UVs, dtype=np.float32)
    if (positions.ndim != 2 or positions.shape[1] != 3 or normals.shape != positions.shape
            or uvs.shape != (len(positions), 2) or not np.isfinite(normals).all()):
        raise ValueError("Geometria inválida para displacement")
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    directions = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 1e-8)
    heights = amostrar_altura(_pixels(resource), uvs)
    return np.ascontiguousarray(positions + directions*(strength*heights[:, None]))
