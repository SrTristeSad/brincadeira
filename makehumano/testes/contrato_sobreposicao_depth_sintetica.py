"""Contrato de duas superfícies e profundidade sintética GL/Vulkan.

Foreground vermelho finito (profundidade normalizada 0.25) e background
azul fullscreen (0.75), sem blending, Phong, textura ou sombras.
Desenha ambas as faces sob MSAA 4x e compara a interação da máscara A2C
com depth-write por amostra, inclusive ordem invertida.
"""
import hashlib

import numpy as np

from auditar_cobertura_a2c_sintetica import (
    VERTICES_ARESTA, VERTICES_TELA, salvar_png_rgb,
)


CASOS_SOBREPOSICAO = (
    ("a2c_off_z_on", False, True, "frente_primeiro"),
    ("a2c_off_z_off", False, False, "frente_primeiro"),
    ("a2c_on_z_on", True, True, "frente_primeiro"),
    ("a2c_on_z_off", True, False, "frente_primeiro"),
    ("a2c_off_z_on_inverso", False, True, "fundo_primeiro"),
    ("a2c_on_z_on_inverso", True, True, "fundo_primeiro"),
    ("a2c_on_z_on_repeticao", True, True, "frente_primeiro"),
)
COR_FRENTE = (255, 0, 0)
COR_FUNDO = (0, 0, 255)
ALFA_FRENTE_A2C = 128
DEPTH_FRENTE = 0.25
DEPTH_FUNDO = 0.75


def vertices_com_profundidade(face):
    if face == "frente":
        vertices, z = VERTICES_ARESTA, DEPTH_FRENTE
    elif face == "fundo":
        vertices, z = VERTICES_TELA, DEPTH_FUNDO
    else:
        raise ValueError("Face sintética não identificada")
    return [(float(x), float(y), float(z)) for x, y in vertices]


def sequencia_draw(a2c, escrita_z, ordem):
    if type(a2c) is not bool or type(escrita_z) is not bool:
        raise ValueError("A2C e depth-write devem ser booleanos")
    if ordem not in ("frente_primeiro", "fundo_primeiro"):
        raise ValueError("Ordem desconhecida")
    frente = {
        "face": "frente",
        "a2c": a2c,
        "escrita_z": escrita_z,
        "depth_test": True,
        "blend": False,
    }
    fundo = {
        "face": "fundo",
        "a2c": False,
        "escrita_z": True,
        "depth_test": True,
        "blend": False,
    }
    return [frente, fundo] if ordem == "frente_primeiro" else [fundo, frente]


def resumir_rgb(rgb):
    a = np.asarray(rgb)
    if a.shape != (64, 64, 3) or a.dtype != np.uint8:
        raise ValueError("RGB8 sintético precisa ter 64x64x3")
    if np.any(a[:, :, 1]):
        raise ValueError("Canal verde deve permanecer zero sem blending")
    a = np.ascontiguousarray(a)
    return {
        "sha256_rgb": hashlib.sha256(a.tobytes()).hexdigest(),
        "centro_rgb": [int(x) for x in a[32, 32]],
        "pixels_com_vermelho": int(np.count_nonzero(a[:, :, 0])),
        "pixels_com_azul": int(np.count_nonzero(a[:, :, 2])),
        "pixels_roxo": int(np.count_nonzero(
            (a[:, :, 0] > 0) & (a[:, :, 2] > 0)
        )),
        "media_r": float(a[:, :, 0].mean()),
        "media_b": float(a[:, :, 2].mean()),
    }


def criar_registro(rgb, arquivo, *, nome, a2c, escrita_z, ordem, rastros):
    esperado = sequencia_draw(a2c, escrita_z, ordem)
    if rastros != esperado:
        raise ValueError("Rastros de estados diferem da sequência solicitada")
    metrica = resumir_rgb(rgb)
    digest_png = salvar_png_rgb(rgb, arquivo)
    return {
        **metrica,
        "nome": nome,
        "amostras": 4,
        "alfa_frente": ALFA_FRENTE_A2C if a2c else 255,
        "a2c_frente": a2c,
        "escrita_z_frente": escrita_z,
        "ordem": ordem,
        "depth_test": True,
        "blending": False,
        "depth_compare": "less",
        "depth_fundo": DEPTH_FUNDO,
        "depth_frente": DEPTH_FRENTE,
        "vertices_frente": vertices_com_profundidade("frente"),
        "vertices_fundo": vertices_com_profundidade("fundo"),
        "rastros_draw": rastros,
        "png": str(arquivo),
        "sha256_png": digest_png,
    }
