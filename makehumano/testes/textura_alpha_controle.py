"""PNG RGBA temporário determinístico para harnesses OpenGL/Vulkan.

O original pode liberar imediatamente um Texture de Image sem sourcePath:
um arquivo permite que ambos os backends carreguem e cacheiem o mesmo PNG.
"""
import hashlib
from pathlib import Path
import struct
import zlib

import numpy as np


def dados_textura_alfa_parcial(lado=32, alfa=128):
    if lado != 32 or alfa not in (64, 128, 192, 255):
        raise ValueError("Controle exige 32×32 RGBA com alfa 64, 128, 192 ou 255")
    y, x = np.indices((lado, lado))
    checker = ((x // 8 + y // 8) % 2) == 0
    pixels = np.zeros((lado, lado, 4), dtype=np.uint8)
    pixels[:, :, :3] = np.where(
        checker[:, :, None], (220, 170, 90), (55, 125, 230)
    )
    pixels[:, :, 3] = alfa
    return np.ascontiguousarray(pixels)


def _chunk_png(tipo, dados):
    crc = zlib.crc32(tipo + dados) & 0xFFFFFFFF
    return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", crc)


def bytes_png_textura_alfa_parcial(*, alfa=128):
    dados = dados_textura_alfa_parcial(alfa=alfa)
    h, w, _ = dados.shape
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    scans = b"".join(b"\x00" + dados[y].tobytes() for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + _chunk_png(b"IHDR", ihdr)
            + _chunk_png(b"IDAT", zlib.compress(scans, 9))
            + _chunk_png(b"IEND", b""))


def salvar_textura_alfa_parcial(caminho, *, alfa=128):
    """Persistência fora do repo, para controles A=64, 128, 192 ou 255."""
    dados = dados_textura_alfa_parcial(alfa=alfa)
    data = bytes_png_textura_alfa_parcial(alfa=alfa)
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)
    return str(destino), {
        "origem": "png_temporario_de_harness",
        "padrao": "xadrez_8x8",
        "formato": "RGBA8",
        "shape": list(dados.shape),
        "alfa_textura": int(alfa),
        "sha256_rgba": hashlib.sha256(dados.tobytes()).hexdigest(),
        "sha256_png": hashlib.sha256(data).hexdigest(),
        "bytes_png": len(data),
    }
