"""Contrato de Z variável: dois triângulos de mesma silhueta que se cruzam.

Teste GPU independente do MakeHumano. Azul plano z=.5; vermelho tem
z=.3/.7/.3 nos três vértices, portanto cruza a profundidade do azul.
Alfa vermelho constante, sem blend, Phong, textura ou sombras.
"""
import hashlib
import numpy as np

from auditar_cobertura_a2c_sintetica import VERTICES_ARESTA, salvar_png_rgb

# nome, A2C vermelho, escreve profundidade vermelha, ordem.
CASOS_CRUZAMENTO = (
    ("off_z_on_vermelho_primeiro", False, True, "vermelho_primeiro"),
    ("off_z_on_azul_primeiro", False, True, "azul_primeiro"),
    ("off_z_off_vermelho_primeiro", False, False, "vermelho_primeiro"),
    ("off_z_off_azul_primeiro", False, False, "azul_primeiro"),
    ("on_z_on_vermelho_primeiro", True, True, "vermelho_primeiro"),
    ("on_z_on_azul_primeiro", True, True, "azul_primeiro"),
    ("on_z_off_vermelho_primeiro", True, False, "vermelho_primeiro"),
    ("on_z_off_azul_primeiro", True, False, "azul_primeiro"),
    ("on_z_on_repeticao", True, True, "vermelho_primeiro"),
)
Z_VERMELHO = (0.30, 0.70, 0.30)
Z_AZUL = 0.50
ALFA_A2C = 128
PROBES_YX = ((32, 32), (42, 45))
FAIXA_Z = 0.030  # largura apenas da ANÁLISE, não altera o depth test


def vertices(face):
    if face == "vermelho":
        depths = Z_VERMELHO
    elif face == "azul":
        depths = (Z_AZUL,) * 3
    else:
        raise ValueError("Face não prevista no ensaio de cruzamento")
    return [
        [float(x), float(y), float(z)]
        for (x, y), z in zip(VERTICES_ARESTA, depths)
    ]


def passos(a2c, z_write, ordem):
    if type(a2c) is not bool or type(z_write) is not bool:
        raise ValueError("A2C/Z precisam ser booleanos")
    if ordem not in ("vermelho_primeiro", "azul_primeiro"):
        raise ValueError("Ordem desconhecida")
    vermelho = {
        "face": "vermelho", "a2c": a2c, "escrita_z": z_write,
        "depth_compare": "less-equal", "depth_test": True, "blend": False,
    }
    azul = {
        "face": "azul", "a2c": False, "escrita_z": True,
        "depth_compare": "less-equal", "depth_test": True, "blend": False,
    }
    return ([vermelho, azul] if ordem == "vermelho_primeiro"
            else [azul, vermelho])


def regioes_analiticas():
    """Máscaras por barycentric no CENTRO do pixel; não revela sample mask."""
    tri = np.asarray(VERTICES_ARESTA, dtype=np.float64)
    matriz = np.vstack((tri.T, np.ones(3)))
    y, x = np.indices((64, 64), dtype=np.float64)
    ndcx = (x + 0.5) / 32.0 - 1.0
    ndcy = 1.0 - (y + 0.5) / 32.0
    coords = np.stack((ndcx.ravel(), ndcy.ravel(), np.ones(4096)))
    bar = np.linalg.solve(matriz, coords).reshape(3, 64, 64)
    interior = np.all(bar > 0.06, axis=0)
    z_vermelho = np.tensordot(
        np.asarray(Z_VERMELHO, dtype=np.float64), bar, axes=(0, 0)
    )
    faixa = interior & (np.abs(z_vermelho - Z_AZUL) <= FAIXA_Z)
    longe = interior & ~faixa
    return {
        "interior_seguranca": interior,
        "faixa_cruzamento": faixa,
        "interior_fora_faixa": longe,
        "borda_ou_exterior": ~interior,
        "vermelho_mais_perto": interior & (z_vermelho < Z_AZUL - FAIXA_Z),
        "azul_mais_perto": interior & (z_vermelho > Z_AZUL + FAIXA_Z),
    }


def classificar_pixel(rgb):
    a = np.asarray(rgb)
    if a.shape != (3,) or a.dtype != np.uint8 or int(a[1]):
        return "invalido"
    r, b = int(a[0]), int(a[2])
    if r == 255 and b == 0:
        return "vermelho"
    if r == 0 and b == 255:
        return "azul"
    if 100 <= r <= 155 and 100 <= b <= 155 and 253 <= r + b <= 256:
        return "misto_a2c"
    return "inesperado"


def classe_esperada(caso, ponto):
    _nome, a2c, z_write, ordem = caso
    if ponto not in PROBES_YX:
        raise ValueError("Probe não definido")
    # Em (32,32) o vermelho está à frente, em (42,45) está atrás.
    if ponto == (42, 45):
        return "azul"
    if not z_write and ordem == "vermelho_primeiro":
        return "azul"
    return "misto_a2c" if a2c else "vermelho"


def registrar(rgb, png, caso, rastros):
    nome, a2c, z_write, ordem = caso
    if rastros != passos(a2c, z_write, ordem):
        raise ValueError("Spy de estados do draw inconsistente")
    a = np.asarray(rgb)
    if a.dtype != np.uint8 or a.shape != (64, 64, 3):
        raise ValueError("RGB cruzamento deve ser uint8 64x64x3")
    if np.any(a[:, :, 1]):
        raise ValueError("Canal G deveria permanecer zero sem blending")
    a = np.ascontiguousarray(a)
    return {
        "nome": nome,
        "a2c_vermelho": a2c,
        "escrita_z_vermelho": z_write,
        "ordem": ordem,
        "depth_compare": "less-equal",
        "amostras": 4,
        "alfa_vermelho": ALFA_A2C if a2c else 255,
        "blend": False,
        "vertices_vermelho": vertices("vermelho"),
        "vertices_azul": vertices("azul"),
        "rastros": rastros,
        "probes_yx": [list(p) for p in PROBES_YX],
        "probes_rgb": [[int(v) for v in a[p]] for p in PROBES_YX],
        "sha256_rgb": hashlib.sha256(a.tobytes()).hexdigest(),
        "pixels_vermelhos": int(np.count_nonzero(a[:, :, 0])),
        "pixels_azuis": int(np.count_nonzero(a[:, :, 2])),
        "pixels_mistos": int(np.count_nonzero(
            (a[:, :, 0] > 0) & (a[:, :, 2] > 0)
        )),
        "png": str(png),
        "sha256_png": salvar_png_rgb(a, png),
    }
