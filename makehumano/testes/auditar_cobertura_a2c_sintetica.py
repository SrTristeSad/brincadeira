"""Contrato compartilhado do ensaio GPU A2C sintético GL/Vulkan.

Sem imagem de personagem, textura, Phong, sombras, blending ou depth.
RGBA8 linear, triângulos de tela cheia ou com aresta subpixel, resolvidos a 64x64.
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
    # Aresta diagonal com vértices em coordenadas subpixel (64x64).
    ("aresta_1x_a255_a2c_off", 1, False, 255),
    ("aresta_4x_a255_a2c_off", 4, False, 255),
    ("aresta_4x_a128_a2c_off", 4, False, 128),
    ("aresta_4x_a255_a2c_on", 4, True, 255),
    ("aresta_4x_a064_a2c_on", 4, True, 64),
    ("aresta_4x_a128_a2c_on", 4, True, 128),
    ("aresta_4x_a192_a2c_on", 4, True, 192),
)

# Todos os backends recebem estes MESMOS vértices no plano de clip.
# As coordenadas mapearão a frações de pixel de 1/8 e 1/4.
VERTICES_TELA = (
    (-1.0, -1.0),
    (3.0, -1.0),
    (-1.0, 3.0),
)
VERTICES_ARESTA = (
    (-0.84765625, -0.78515625),
    (0.91015625, -0.59765625),
    (-0.34765625, 0.91015625),
)

# Deslocamentos em PIXELS da grade do framebuffer 64x64, compartilhados
# por OpenGL e Vulkan. 1 px equivale a 2/64 em coordenadas NDC.
# A origem é o ensaio precedente, não se desloca o produto para casar CI.
DESLOCAMENTOS_SUBPIXEL = (
    ("dx_m025", -0.25, 0.0),
    ("dx_p025", +0.25, 0.0),
    ("dy_m025", 0.0, -0.25),
    ("dy_p025", 0.0, +0.25),
)

CASOS += tuple(
    (
        "aresta_{}_4x_a{:03d}_a2c_{}".format(
            rotulo, alfa, "on" if a2c else "off"
        ),
        4, a2c, alfa,
    )
    for rotulo, _dx, _dy in DESLOCAMENTOS_SUBPIXEL
    for a2c, alfa in ((False, 255), (True, 128))
)


def deslocamento_do_caso(nome):
    if not nome.startswith("aresta_"):
        return (0.0, 0.0)
    for rotulo, dx, dy in DESLOCAMENTOS_SUBPIXEL:
        if nome.startswith("aresta_" + rotulo + "_"):
            return (dx, dy)
    return (0.0, 0.0)


def vertices_do_caso(nome):
    if nome.startswith("aresta_"):
        dx, dy = deslocamento_do_caso(nome)
        # dy é deslocamento no eixo NDC; no PNG com origem no topo,
        # deslocamento vertical aparente tem sinal invertido.
        return tuple(
            (x + dx * 2.0 / 64.0, y + dy * 2.0 / 64.0)
            for x, y in VERTICES_ARESTA
        )
    if nome.startswith(("1x_", "4x_")):
        return VERTICES_TELA
    raise ValueError("Geometria sintética desconhecida: " + str(nome))


def geometria_do_caso(nome):
    vertices_do_caso(nome)  # valida o nome
    return "aresta_subpixel" if nome.startswith("aresta_") else "tela_cheia"



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
