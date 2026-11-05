"""Exportação OBJ da malha corporal deformada, sem dependências Qt/GPU.

Preserva os índices dos vértices CANÔNICOS do MakeHuman e as costuras UV.
Apenas o grupo corporal atualmente renderizado é incluído nas faces; não
exporta roupas, esqueleto, materiais avançados nem rigging. O formato OBJ
não representa todos os detalhes de um projeto .mhm.
"""

import os
from pathlib import Path
import tempfile

import numpy as np

from .malha import Malha


def _validar(malha: Malha, vertices: np.ndarray) -> np.ndarray:
    dados = np.asarray(vertices)
    if dados.shape != malha.vertices.shape or dados.ndim != 2 or dados.shape[1] != 8:
        raise ValueError("Buffers de vértices incompatíveis com a malha carregada")
    if not np.issubdtype(dados.dtype, np.floating):
        raise ValueError("Os vértices precisam conter números reais")
    if not np.isfinite(dados).all():
        raise ValueError("Vértices contêm valores não finitos")

    n_render = len(dados)
    if (malha.indices.ndim != 1 or len(malha.indices) % 3
            or not len(malha.indices)
            or np.any(malha.indices >= n_render)):
        raise ValueError("Índices de faces inválidos")
    if malha.origens.shape != (n_render,):
        raise ValueError("Mapeamento dos vértices originais inválido")
    if np.any(malha.origens >= len(malha.posicoes_base)):
        raise ValueError("A malha referencia vértices inexistentes")
    if malha.posicoes_base.ndim != 2 or malha.posicoes_base.shape[1] != 3:
        raise ValueError("Vértices canônicos inválidos")

    # Duas entradas de renderização que representam o mesmo vértice OBJ
    # precisam ter posições idênticas, embora possam ter UVs diferentes.
    anteriores = np.full(len(malha.posicoes_base), -1, dtype=np.int64)
    for i, origem in enumerate(malha.origens):
        primeiro = anteriores[origem]
        if primeiro >= 0 and not np.allclose(
            dados[i, :3], dados[primeiro, :3], rtol=0, atol=1e-5
        ):
            raise ValueError("Costura UV contém posições divergentes")
        anteriores[origem] = i
    return dados


def exportar_obj(caminho: str | Path, malha: Malha, vertices: np.ndarray) -> Path:
    """Escreve OBJ triangulado com v, vt, vn e f; preserva índices MakeHuman.

    UVs em memoria usam a convenção wgpu, de origem superior. O formato
    OBJ original utiliza origem inferior: portanto vt = (u, 1-v).
    O arquivo é gravado em temporário e substituído atomicamente.
    """
    dados = _validar(malha, vertices)
    destino = Path(caminho)
    if destino.suffix.lower() != ".obj":
        raise ValueError("A exportação precisa de um destino .obj")

    posicoes = malha.posicoes_base.copy()
    posicoes[malha.origens] = dados[:, :3]
    formato = ".9g"  # Precision suficiente para recuperar coordenadas float32
    temporario = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=destino.parent,
            prefix=".makehumano-export-", suffix=".tmp", delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write("# MakeHumano - geometria corporal deformada\n")
            arquivo.write("# Faces trianguladas; índices originais preservados\n")
            arquivo.write("# Sem esqueleto, roupas ou textura incorporada\n")

            for p in posicoes:
                arquivo.write("v " + " ".join(format(float(v), formato) for v in p) + "\n")
            for uv in dados[:, 6:8]:
                arquivo.write(
                    "vt " + format(float(uv[0]), formato) + " "
                    + format(1.0 - float(uv[1]), formato) + "\n"
                )
            for n in dados[:, 3:6]:
                arquivo.write("vn " + " ".join(format(float(v), formato) for v in n) + "\n")

            arquivo.write("g body\n")
            for tria in malha.indices.reshape(-1, 3):
                pontos = []
                for indice in tria:
                    indice = int(indice)
                    # Posição original; UV/normal no vértice renderizado.
                    pos = int(malha.origens[indice]) + 1
                    uv_normal = indice + 1
                    pontos.append(f"{pos}/{uv_normal}/{uv_normal}")
                arquivo.write("f " + " ".join(pontos) + "\n")

        os.replace(temporario, destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return destino
