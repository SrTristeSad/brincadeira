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
from .materiais import (mapa_normal_neutro, mapa_rugosidade_neutro)
from .materiais_obj import (
    NOME_MATERIAL, caminhos_materiais, caminhos_mapas, validar_material,
    escrever_png_rgba, texto_mtl,
)


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


def exportar_obj(
    caminho: str | Path, malha: Malha, vertices: np.ndarray,
    *, arquivo_mtl: str | None = None,
) -> Path:
    """Escreve OBJ triangulado com v, vt, vn e f; preserva índices MakeHuman.

    UVs em memoria usam a convenção wgpu, de origem superior. O formato
    OBJ original utiliza origem inferior: portanto vt = (u, 1-v).
    O arquivo é gravado em temporário e substituído atomicamente.
    """
    dados = _validar(malha, vertices)
    if arquivo_mtl is not None and (
        not arquivo_mtl or '/' in arquivo_mtl or '\\' in arquivo_mtl
        or '\n' in arquivo_mtl or '\r' in arquivo_mtl
    ):
        raise ValueError('Nome de arquivo MTL inválido')
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
            if arquivo_mtl is not None:
                arquivo.write(f"mtllib {arquivo_mtl}\n")

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
            if arquivo_mtl is not None:
                arquivo.write(f"usemtl {NOME_MATERIAL}\n")
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


def exportar_obj_com_material(
    caminho: str | Path, malha: Malha, vertices: np.ndarray,
    pele, textura_rgba=None, *,
    mapa_normal_rgba=None, mapa_rugosidade_rgba=None,
) -> tuple[Path, Path, Path]:
    """Exporta OBJ, MTL, PNG difuso e mapas auxiliares de normal/rugosidade.

    Os três arquivos são preparados com validação prévia. Substituições são
    atômicas por arquivo (não existe transação atômica entre três arquivos).
    OBJ é publicado por último para evitar referências a arquivos ausentes
    no caso normal de exportações novas.
    """
    destino = Path(caminho)
    if destino.suffix.lower() != ".obj":
        raise ValueError("A exportação precisa de um destino .obj")
    _validar(malha, vertices)
    rgba = validar_material(pele, textura_rgba)
    normal = validar_material(
        pele, mapa_normal_neutro() if mapa_normal_rgba is None else mapa_normal_rgba
    )
    rugosidade = validar_material(
        pele, mapa_rugosidade_neutro()
        if mapa_rugosidade_rgba is None else mapa_rugosidade_rgba
    )
    mtl, png = caminhos_materiais(destino)
    png_normal, png_rugosidade = caminhos_mapas(destino)
    texto = texto_mtl(pele, png.name)
    temporarios = []
    try:
        # Primeiro gerar ambos os recursos com nomes temporários.
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=destino.parent,
            prefix=".makehumano-png-", suffix=".tmp", delete=False,
        ) as arquivo:
            tmp_png = Path(arquivo.name)
        temporarios.append(tmp_png)
        escrever_png_rgba(tmp_png, rgba)

        # Mapas PBR acompanham o OBJ como arquivos auxiliares. O MTL clássico
        # só referencia o mapa difuso; não rotulamos normais como altura/bump.
        extras = []
        for destino_mapa, pixels_mapa in (
            (png_normal, normal), (png_rugosidade, rugosidade)
        ):
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destino.parent,
                prefix=".makehumano-mapa-", suffix=".tmp", delete=False,
            ) as arquivo:
                temporario_mapa = Path(arquivo.name)
            temporarios.append(temporario_mapa)
            escrever_png_rgba(temporario_mapa, pixels_mapa)
            extras.append((temporario_mapa, destino_mapa))

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=destino.parent,
            prefix=".makehumano-mtl-", suffix=".tmp", delete=False,
        ) as arquivo:
            tmp_mtl = Path(arquivo.name)
            temporarios.append(tmp_mtl)
            arquivo.write(texto)

        os.replace(tmp_png, png)
        for origem_mapa, destino_mapa in extras:
            os.replace(origem_mapa, destino_mapa)
        os.replace(tmp_mtl, mtl)
        exportar_obj(destino, malha, vertices, arquivo_mtl=mtl.name)
    finally:
        for temporario in temporarios:
            temporario.unlink(missing_ok=True)
    return destino, mtl, png
