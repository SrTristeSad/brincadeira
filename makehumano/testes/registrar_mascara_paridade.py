"""Máscara alfa real de mh.renderAlphaMask; apenas harnesses isolados.

Renderiza o valor medido como A em PNG RGBA. RGB propositalmente zero.
Não importa nem modifica backends de renderização.
"""
import hashlib
from pathlib import Path
import numpy as np


def extrair_mascara_api(imagem, *, largura=1024, altura=768):
    """Valida grayscale RGB original, rejeitando imagem colorida ou alfa opaco."""
    array = np.asarray(imagem.data)
    if array.shape != (altura, largura, 3) or array.dtype != np.uint8:
        raise ValueError(
            f"renderAlphaMask precisa de cinza RGB uint8 {largura}x{altura}: "
            f"{array.shape} {array.dtype}"
        )
    if (not np.array_equal(array[:, :, 0], array[:, :, 1])
            or not np.array_equal(array[:, :, 0], array[:, :, 2])):
        raise ValueError("renderAlphaMask retornou RGB não cinza")
    alpha = np.ascontiguousarray(array[:, :, 0])
    if not np.any(alpha == 0) or not np.any(alpha > 0):
        raise ValueError("Máscara vazia ou inteiramente opaca não prova cobertura")
    rgba = np.zeros((altura, largura, 4), dtype=np.uint8)
    rgba[:, :, 3] = alpha
    stats = {
        "origem": "mh.renderAlphaMask",
        "largura": int(largura), "altura": int(altura),
        "alfa_min": int(alpha.min()), "alfa_max": int(alpha.max()),
        "alfa_zero": int(np.count_nonzero(alpha == 0)),
        "alfa_nao_zero": int(np.count_nonzero(alpha > 0)),
        "alfa_intermediario": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
        "sha256_alfa": hashlib.sha256(alpha.tobytes()).hexdigest(),
        "saida_rgb_original_grayscale": True,
        "png_rgba_canais_rgb_zerados": True,
    }
    return rgba, stats


def registrar_mascara(imagem, caminho_png):
    """Salva RGBA com A medido, via Image original do MakeHuman."""
    from image import Image
    rgba, stats = extrair_mascara_api(imagem)
    caminho = Path(caminho_png)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image(data=rgba).save(str(caminho))
    stats.update({
        "arquivo_png_rgba": str(caminho),
        "sha256_png_rgba": hashlib.sha256(caminho.read_bytes()).hexdigest(),
    })
    return stats
