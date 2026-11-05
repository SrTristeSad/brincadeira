"""Transformações de offsets para proxies MakeHuman com shear.

Reproduz a construção de caixas de TMatrix.matrixFromShear(), mas calcula
a transformação afim por mínimos quadrados em NumPy. Proxies com escalas
x/y/z continuam no caminho diagonal original.
"""

import numpy as np


def matriz_cisalhamento(entradas, coordenadas):
    """Retorna matriz 3×3 equivalente à parte linear de matrixFromShear.

    entradas: sequência de três (índice_1, índice_2, origem_1, origem_2),
    uma para cada eixo. O MakeHuman ajusta uma transformação afim entre
    oito cantos das caixas de referência e deformada.
    """
    corpo = np.asarray(coordenadas, dtype=np.float64)
    if corpo.ndim != 2 or corpo.shape[1] != 3 or not np.isfinite(corpo).all():
        raise ValueError("Coordenadas do corpo inválidas")
    if len(entradas) != 3:
        raise ValueError("Shear exige três eixos completos")
    origem = np.empty((3, 2), dtype=np.float64)
    destino = np.empty((3, 2), dtype=np.float64)
    for eixo, entrada in enumerate(entradas):
        if len(entrada) != 4:
            raise ValueError("Shear precisa de quatro parâmetros por eixo")
        a, b, u, v = entrada
        if not 0 <= a < len(corpo) or not 0 <= b < len(corpo):
            raise ValueError("Referência de shear fora do corpo")
        if not np.isfinite(u) or not np.isfinite(v):
            raise ValueError("Origem de shear não finita")
        origem[eixo, :] = (u, v)
        destino[eixo, :] = (corpo[a, eixo], corpo[b, eixo])
    if np.any(np.abs(origem[:, 1] - origem[:, 0]) < 1e-8):
        raise ValueError("Caixa original de shear degenerada")

    # Mesma ordem dos oito cantos do método original.
    combinacoes = ((i, j, k) for i in (0, 1)
                   for j, k in ((0, 0), (0, 1), (1, 1), (1, 0)))
    cantos = list(combinacoes)
    sbox = np.asarray(
        [[origem[eixo, escolha[eixo]] for eixo in range(3)]
         for escolha in cantos], dtype=np.float64,
    )
    tbox = np.asarray(
        [[destino[eixo, escolha[eixo]] for eixo in range(3)]
         for escolha in cantos], dtype=np.float64,
    )
    s0 = sbox - np.mean(sbox, axis=0)
    t0 = tbox - np.mean(tbox, axis=0)
    # A origem da caixa é ortogonal nos três eixos; o ajuste da parte
    # linear da transformação é determinado exatamente por estes cantos.
    mat, _, rank, _ = np.linalg.lstsq(s0, t0, rcond=None)
    if rank != 3 or not np.isfinite(mat).all():
        raise ValueError("Não foi possível calcular o shear")
    return np.ascontiguousarray(mat.T, dtype=np.float32)
