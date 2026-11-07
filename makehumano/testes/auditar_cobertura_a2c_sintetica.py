"""Contrato compartilhado do ensaio GPU A2C sintético GL/Vulkan.

Sem imagem de personagem, textura, Phong, sombras, blending ou depth.
RGBA8 linear, triângulo de tela cheia, framebuffer resolvido a 64x64.
Não presume quantização específica das implementações de A2C.
"""
import hashlib
import struct
import zlib
from pathlib import Path

import numpy as np


CASOS = (
    ("1x_a128_a2c_off", 1, False, 128),
    ("4x_a128_a2c_off", 4, False, 128),
    ("4x_a000_a2c_on", 4, True, 0),
    ("4x_a064_a2c_on", 4, True, 64),
    ("4x_a128_a2c_on", 4, True, 128),
    ("4x_a192_a2c_on", 4, True, 192),
    ("4x_a255_a2c_on", 4, True, 255),
)


def registrar_rgb(rgb):
    a = np.asarray(rgb)
    if a.dtype != np.uint8 or a.shape != (64, 64, 3):
        raise ValueError("RGB sintético exige uint8 64×64×3")
    rgb = np.ascontiguousarray(a)
    # Upstream MakeHuman pode substituir numpy.unique por uma versão
    # sem return_counts; usar bincount evita a incompatibilidade no legado.
    contagens = np.bincount(rgb[:, :, 0].ravel(), minlength=256)
    if not np.array_equal(rgb[:, :, 0], rgb[:, :, 1]) or not np.array_equal(
        rgb[:, :, 0], rgb[:, :, 2]
    ):
        raise ValueError("Shader sintético branco deve gerar canais R=G=B")
    return {
        "sha256_rgb": hashlib.sha256(rgb.tobytes()).hexdigest(),
        "histograma_r": {
            str(i): int(n) for i, n in enumerate(contagens) if n
        },
        "media_r": float(np.mean(rgb[:, :, 0])),
        "pixels": int(rgb.shape[0] * rgb.shape[1]),
    }


def salvar_png_rgb(rgb, arquivo):
    """PNG RGB8 determinístico com stdlib, sem depender de Pillow no harness."""
    a = np.asarray(rgb)
    if a.dtype != np.uint8 or a.shape != (64, 64, 3):
        raise ValueError("Formato PNG diagnóstico inválido")
    a = np.ascontiguousarray(a)
    raw = b"".join(b"\x00" + row.tobytes() for row in a)
    def chunk(tag, data):
        payload = tag + data
        return (
            struct.pack(">I", len(data)) + payload +
            struct.pack(">I", zlib.crc32(payload) & 0xffffffff)
        )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, level=6))
        + chunk(b"IEND", b"")
    )
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(png)
    return hashlib.sha256(png).hexdigest()
