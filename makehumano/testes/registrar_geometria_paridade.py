"""Assinaturas de malha para diagnóstico OpenGL/Vulkan sem renderer importado.

Buffers canonizados em little-endian e float32/uint32; independem da
versão NumPy, ordem da memória, e caminhos de checkout.
"""
import hashlib

import numpy as np


def _assinar(valores, dtype, dimensoes):
    arr = np.asarray(valores, dtype=dtype)
    if arr.ndim != len(dimensoes) or any(
        esperado is not None and atual != esperado
        for atual, esperado in zip(arr.shape, dimensoes)
    ):
        raise ValueError(f"Buffer inválido: shape={arr.shape}; esperado={dimensoes}")
    if arr.dtype.kind == "f" and not np.isfinite(arr).all():
        raise ValueError("Buffer de malha contém NaN/inf")
    normalizado = np.ascontiguousarray(arr)
    return {
        "dtype": str(normalizado.dtype),
        "shape": list(normalizado.shape),
        "sha256": hashlib.sha256(normalizado.tobytes()).hexdigest(),
    }


def descrever_geometria(mundo, material):
    """Registra o corpo real selecionado, sem alterar nem copiar a geometria GPU."""
    objetos = [
        obj for obj in mundo
        if getattr(obj, "material", None) is material
        and getattr(obj, "visibility", True)
        and getattr(obj, "solid", True)
    ]
    if not objetos:
        raise RuntimeError("Corpo original ausente de G.world")
    corpo = max(objetos, key=lambda obj: len(obj.primitives))
    pos = np.asarray(corpo.verts, dtype="<f4")
    norms = np.asarray(corpo.norms, dtype="<f4")
    indices = np.asarray(corpo.primitives, dtype="<u4")
    if pos.ndim != 2 or pos.shape[-1] != 3:
        raise ValueError("Posições não são [N,3]")
    assinaturas = {
        "posicoes": _assinar(pos, "<f4", (len(pos), 3)),
        "normais": _assinar(norms, "<f4", (len(pos), 3)),
        "primitivas": _assinar(indices, "<u4", (None, 4)),
    }
    modulos = np.linalg.norm(norms.astype(np.float64), axis=1)
    return {
        "objeto": str(corpo.name),
        "cameraMode": int(corpo.cameraMode),
        "quantidade_vertices": int(len(pos)),
        "quantidade_faces": int(len(indices)),
        "assinaturas": assinaturas,
        "normais_modulo_min": float(modulos.min()),
        "normais_modulo_max": float(modulos.max()),
        "normais_modulo_medio": float(modulos.mean()),
        "bbox_min": pos.min(axis=0).astype(float).tolist(),
        "bbox_max": pos.max(axis=0).astype(float).tolist(),
    }
