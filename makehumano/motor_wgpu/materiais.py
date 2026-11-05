"""Controles básicos de material da pele e pixels RGBA independentes da GPU."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Pele:
    cor: tuple[float, float, float] = (1.0, 0.83, 0.72)
    rugosidade: float = 0.65
    dispersao: float = 0.25  # efeito artístico, não é SSS físico

    def __post_init__(self):
        self.atualizar(cor=self.cor, rugosidade=self.rugosidade,
                       dispersao=self.dispersao)

    def atualizar(self, *, cor=None, rugosidade=None, dispersao=None):
        if cor is not None:
            if len(cor) != 3 or any(not (0.0 <= float(c) <= 1.0) for c in cor):
                raise ValueError("A cor deve ter três canais entre 0 e 1")
            self.cor = tuple(float(c) for c in cor)
        if rugosidade is not None:
            if not (0.05 <= float(rugosidade) <= 1):
                raise ValueError("Rugosidade deve ficar entre 0.05 e 1")
            self.rugosidade = float(rugosidade)
        if dispersao is not None:
            if not (0.0 <= float(dispersao) <= 1.0):
                raise ValueError("Dispersão precisa ficar entre 0 e 1")
            self.dispersao = float(dispersao)


def validar_rgba(pixels) -> np.ndarray:
    """Aceita pixels (altura, largura, 4), contíguos e em uint8."""
    imagem = np.asarray(pixels)
    if imagem.ndim != 3 or imagem.shape[2] != 4 or imagem.dtype != np.uint8:
        raise ValueError("Textura precisa ser imagem RGBA com dtype uint8")
    if not imagem.shape[0] or not imagem.shape[1]:
        raise ValueError("A textura não pode ser vazia")
    return np.ascontiguousarray(imagem)


def textura_neutra() -> np.ndarray:
    """Textura branca para que a tonalidade venha do material por padrão."""
    return np.full((4, 4, 4), 255, dtype=np.uint8)


def mapa_normal_neutro() -> np.ndarray:
    """Normal tangente aproximada (0, 0, 1), em RGB linear."""
    pixels = np.empty((4, 4, 4), dtype=np.uint8)
    pixels[..., 0:2] = 128
    pixels[..., 2:4] = 255
    return pixels


def mapa_rugosidade_neutro() -> np.ndarray:
    """Fator multiplicativo 1: preserva o slider de rugosidade."""
    return np.full((4, 4, 4), 255, dtype=np.uint8)
