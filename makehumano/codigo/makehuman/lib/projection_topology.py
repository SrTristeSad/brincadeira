"""Arestas UV originais, sem compactar índices em campos de 16 bits."""
import numpy as np


def arestas_uv(faces):
    """Pares únicos não orientados, preservando índices de malhas grandes."""
    faces = np.asarray(faces)
    if faces.ndim != 2 or faces.shape[1] < 2 or faces.dtype.kind not in 'iu':
        raise ValueError('Faces UV devem ser uma matriz de índices inteiros')
    if np.any(faces < 0) or np.any(faces > np.iinfo(np.uint32).max):
        raise ValueError('Índices UV fora do intervalo uint32')
    edges = np.stack((faces, np.roll(faces, 1, axis=1)), axis=-1).reshape(-1, 2)
    edges = np.sort(edges, axis=1)
    edges = edges[edges[:, 0] != edges[:, 1]]
    return np.ascontiguousarray(np.unique(edges, axis=0), dtype=np.uint32)
