"""Captura da viewport Vulkan do MakeHuman original, sem glReadPixels.

A captura utiliza a imagem já apresentada pelo QRenderWidget. Isso não
substitui renderização offscreen em resolução independente.
"""

import numpy as np


def recortar_captura_rgb(pixels, x, y, width, height, *, cinza=127):
    """Recorta pixels RGB em coordenadas Qt (origem superior esquerda).

    Regiões fora da viewport são preenchidas com cinza; o tamanho retornado
    corresponde sempre ao solicitado, inclusive para recortes parciais.
    """
    if width <= 0 or height <= 0:
        raise RuntimeError("width or height is 0")
    fonte = np.asarray(pixels)
    if fonte.ndim != 3 or fonte.shape[2] != 3 or fonte.dtype != np.uint8:
        raise ValueError("Captura Vulkan: esperado RGB uint8 [altura, largura, 3]")
    x, y, width, height = map(int, (x, y, width, height))
    original_h, original_w = fonte.shape[:2]
    saida = np.full((height, width, 3), cinza, dtype=np.uint8)
    esquerda, topo = max(0, x), max(0, y)
    direita, base = min(original_w, x + width), min(original_h, y + height)
    if esquerda < direita and topo < base:
        dx, dy = esquerda - x, topo - y
        saida[dy:dy + base - topo, dx:dx + direita - esquerda] = (
            fonte[topo:base, esquerda:direita]
        )
    return np.ascontiguousarray(saida)
