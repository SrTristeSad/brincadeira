"""Casos isolados de Z igual e quase igual para GL/Vulkan.

Duas faces com EXATAMENTE o mesmo triângulo e depth 0.5; no controle
quase coplanar, vermelho está 2^-18 mais perto. Cor RGB plana e sem blend.
Todas as diferenças devem ser descritas, nunca corrigidas por offsets.
"""
import hashlib

import numpy as np
from auditar_cobertura_a2c_sintetica import VERTICES_ARESTA, salvar_png_rgb


# nome, funcao-Z, A2C vermelho, escrita-Z vermelho, ordem, distancia-Z
CASOS_COPLANARES = (
    ("igual_less_off_z_on_vermelho_primeiro", "less", False, True, "vermelho_primeiro", 0.0),
    ("igual_less_off_z_on_azul_primeiro", "less", False, True, "azul_primeiro", 0.0),
    ("igual_lequal_off_z_on_vermelho_primeiro", "less-equal", False, True, "vermelho_primeiro", 0.0),
    ("igual_lequal_off_z_on_azul_primeiro", "less-equal", False, True, "azul_primeiro", 0.0),
    ("igual_less_off_z_off_vermelho_primeiro", "less", False, False, "vermelho_primeiro", 0.0),
    ("igual_less_on_z_on_vermelho_primeiro", "less", True, True, "vermelho_primeiro", 0.0),
    ("igual_less_on_z_on_azul_primeiro", "less", True, True, "azul_primeiro", 0.0),
    ("igual_lequal_on_z_on_vermelho_primeiro", "less-equal", True, True, "vermelho_primeiro", 0.0),
    ("igual_lequal_on_z_on_azul_primeiro", "less-equal", True, True, "azul_primeiro", 0.0),
    ("igual_less_on_z_off_vermelho_primeiro", "less", True, False, "vermelho_primeiro", 0.0),
    ("perto_less_off_z_on_vermelho_primeiro", "less", False, True, "vermelho_primeiro", 2 ** -18),
    ("perto_less_off_z_on_azul_primeiro", "less", False, True, "azul_primeiro", 2 ** -18),
    ("perto_less_on_z_on_vermelho_primeiro", "less", True, True, "vermelho_primeiro", 2 ** -18),
    ("perto_less_on_z_on_azul_primeiro", "less", True, True, "azul_primeiro", 2 ** -18),
    ("igual_less_on_z_on_repeticao", "less", True, True, "vermelho_primeiro", 0.0),
)
DEPTH_AZUL = 0.5
ALFA_VERMELHO = 128
DEPTH_SEPARACAO = 2 ** -18


def vertices_face(face, separacao):
    if face not in ("vermelho", "azul"):
        raise ValueError("Face coplanar desconhecida")
    if separacao not in (0.0, DEPTH_SEPARACAO):
        raise ValueError("Separação de depth inesperada")
    z = DEPTH_AZUL - separacao if face == "vermelho" else DEPTH_AZUL
    return [[float(x), float(y), float(z)] for x, y in VERTICES_ARESTA]


def passos_desenho(comparacao, a2c, escrita_z, ordem):
    if comparacao not in ("less", "less-equal"):
        raise ValueError("Função de comparação inválida")
    if type(a2c) is not bool or type(escrita_z) is not bool:
        raise ValueError("Estados A2C e escrita-Z devem ser booleanos")
    if ordem not in ("vermelho_primeiro", "azul_primeiro"):
        raise ValueError("Ordem de coplanares inválida")
    vermelho = {
        "face": "vermelho", "a2c": a2c,
        "escrita_z": escrita_z, "depth_compare": comparacao,
        "depth_test": True, "blend": False,
    }
    azul = {
        "face": "azul", "a2c": False,
        "escrita_z": True, "depth_compare": comparacao,
        "depth_test": True, "blend": False,
    }
    return ([vermelho, azul] if ordem == "vermelho_primeiro"
            else [azul, vermelho])


def classificar_centro(rgb):
    a = np.asarray(rgb)
    if a.dtype != np.uint8 or a.shape != (64, 64, 3):
        raise ValueError("Imagem coplanar deve ser RGB8 64x64")
    if np.any(a[:, :, 1]):
        raise ValueError("Sem blend, canal verde deve permanecer zero")
    r, _, b = [int(x) for x in a[32, 32]]
    if (r, b) == (255, 0):
        return "vermelho"
    if (r, b) == (0, 255):
        return "azul"
    if 100 <= r <= 155 and 100 <= b <= 155 and 253 <= r + b <= 256:
        return "misto_a2c_4x"
    return "inesperado"


def centro_esperado(comparacao, a2c, escrita_z, ordem, separacao):
    passos_desenho(comparacao, a2c, escrita_z, ordem)
    if separacao not in (0.0, DEPTH_SEPARACAO):
        raise ValueError("Separação de depth inválida")
    if separacao > 0:
        return "misto_a2c_4x" if a2c else "vermelho"
    if ordem == "vermelho_primeiro":
        if not escrita_z or comparacao == "less-equal":
            return "azul"
        return "misto_a2c_4x" if a2c else "vermelho"
    if comparacao == "less":
        return "azul"
    return "misto_a2c_4x" if a2c else "vermelho"


def registrar_captura(rgb, arquivo, caso, rastros):
    nome, comparacao, a2c, escrita_z, ordem, separacao = caso
    if rastros != passos_desenho(comparacao, a2c, escrita_z, ordem):
        raise ValueError("Estado do draw não corresponde ao contrato")
    rgb = np.ascontiguousarray(rgb)
    classe = classificar_centro(rgb)
    resumo = {
        "sha256_rgb": hashlib.sha256(rgb.tobytes()).hexdigest(),
        "centro_rgb": [int(x) for x in rgb[32, 32]],
        "centro_classe": classe,
        "pixels_vermelho": int(np.count_nonzero(rgb[:, :, 0])),
        "pixels_azul": int(np.count_nonzero(rgb[:, :, 2])),
        "pixels_mistos": int(np.count_nonzero(
            (rgb[:, :, 0] > 0) & (rgb[:, :, 2] > 0)
        )),
    }
    return {
        **resumo,
        "nome": nome,
        "comparacao_depth": comparacao,
        "a2c_vermelho": a2c,
        "alfa_vermelho": ALFA_VERMELHO if a2c else 255,
        "escrita_z_vermelho": escrita_z,
        "ordem": ordem,
        "separacao_depth": float(separacao),
        "depth_azul": DEPTH_AZUL,
        "depth_vermelho": DEPTH_AZUL - separacao,
        "vertices_vermelho": vertices_face("vermelho", separacao),
        "vertices_azul": vertices_face("azul", separacao),
        "msaa": 4,
        "formato_cor": "rgba8unorm",
        "blend": False,
        "rastros": rastros,
        "arquivo_png": str(arquivo),
        "sha256_png": salvar_png_rgb(rgb, arquivo),
    }
