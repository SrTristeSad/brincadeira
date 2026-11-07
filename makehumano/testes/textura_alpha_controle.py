"""Textura RGBA determinística de diagnóstico; só usada nos harnesses descartáveis."""
import hashlib
import numpy as np


def dados_textura_alfa_parcial(lado=32, alfa=128):
    if lado != 32 or alfa != 128:
        raise ValueError("O controle deve ser sempre 32×32 RGBA com alfa 128")
    y, x = np.indices((lado, lado))
    checker = ((x // 8 + y // 8) % 2) == 0
    pixels = np.zeros((lado, lado, 4), dtype=np.uint8)
    pixels[:, :, :3] = np.where(
        checker[:, :, None], (220, 170, 90), (55, 125, 230)
    )
    pixels[:, :, 3] = alfa
    return np.ascontiguousarray(pixels)


def construir_textura_alfa_parcial():
    """Image instanciada no runtime original; nenhuma dependência no módulo."""
    from image import Image
    dados = dados_textura_alfa_parcial()
    meta = {
        "origem": "rgba_em_memoria",
        "padrao": "xadrez_8x8",
        "formato": "RGBA8",
        "shape": list(dados.shape),
        "alfa_textura": 128,
        "sha256_rgba": hashlib.sha256(dados.tobytes()).hexdigest(),
    }
    return Image(data=dados), meta
