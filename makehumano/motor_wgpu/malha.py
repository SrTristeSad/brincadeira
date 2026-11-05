"""Leitor OBJ com UVs do MakeHuman, isolado de Qt e da GPU."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Malha:
    vertices: np.ndarray  # float32 [x,y,z,nx,ny,nz,u,v]
    indices: np.ndarray   # uint32: triângulos
    posicoes_base: np.ndarray  # float32 [n,3]: vértices originais OBJ
    origens: np.ndarray        # uint32 [m]: índice OBJ por vértice renderizado
    faces_base: np.ndarray     # uint32 [triângulos,3]: topologia no OBJ


def calcular_normais(posicoes: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Normais suaves ponderadas pela área, calculadas nos vértices OBJ originais.

    Calculá-las antes de duplicar vértices nas costuras UV evita linhas visíveis
    quando os morph targets atualizam a geometria.
    """
    normais = np.zeros_like(posicoes, dtype=np.float32)
    tris = posicoes[faces]
    vetores = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    for coluna in range(3):
        np.add.at(normais, faces[:, coluna], vetores)
    magnitude = np.linalg.norm(normais, axis=1)
    normais /= np.maximum(magnitude[:, None], 1e-9)
    return normais


def carregar_obj(arquivo: str | Path, grupo: str = "body") -> Malha:
    """Carrega o grupo *body* do base.obj original (quads triangulados).

    O OBJ contém índices independentes de posição e UV, então criamos um vértice
    para cada par (posição, UV). Normais são calculadas na malha original para
    manter a suavização também nas costuras de textura.
    """
    pontos: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[list[tuple[int, int]]] = []
    ativo = grupo is None
    viu_grupo = False
    with Path(arquivo).open(encoding="utf-8") as entrada:
        for linha in entrada:
            partes = linha.split()
            if not partes or partes[0].startswith("#"):
                continue
            tag = partes[0]
            if tag == "v":
                pontos.append(tuple(map(float, partes[1:4])))
            elif tag == "vt":
                uvs.append(tuple(map(float, partes[1:3])))
            elif tag == "g":
                viu_grupo = True
                ativo = grupo is None or grupo in partes[1:]
            elif tag == "f" and ativo:
                face = []
                for token in partes[1:]:
                    campos = token.split("/")
                    vi = int(campos[0])
                    ti = int(campos[1]) if len(campos) > 1 and campos[1] else 0
                    vi = vi - 1 if vi > 0 else len(pontos) + vi
                    ti = ti - 1 if ti > 0 else (len(uvs) + ti if ti < 0 else -1)
                    if not (0 <= vi < len(pontos)):
                        raise ValueError("Índice de vértice OBJ inválido")
                    if ti != -1 and not (0 <= ti < len(uvs)):
                        raise ValueError("Índice de UV OBJ inválido")
                    face.append((vi, ti))
                if len(face) < 3:
                    raise ValueError("Face OBJ com menos de três vértices")
                faces.append(face)

    if not pontos or not faces:
        raise ValueError(f"Nenhuma face carregada do grupo {grupo!r} em {arquivo}")

    coords = np.asarray(pontos, dtype=np.float32)
    triangulos = []
    for face in faces:
        for i in range(1, len(face) - 1):
            triangulos.append((face[0], face[i], face[i + 1]))

    faces_base = np.asarray(
        [[pos for pos, _uv in tri] for tri in triangulos],
        dtype=np.uint32,
    )
    normais = calcular_normais(coords, faces_base)
    mapa: dict[tuple[int, int], int] = {}
    vertices = []
    indices = []
    origens = []
    for tri in triangulos:
        for pos, tex in tri:
            chave = (pos, tex)
            if chave not in mapa:
                u, v = uvs[tex] if tex >= 0 else (0.0, 0.0)
                mapa[chave] = len(vertices)
                vertices.append([*coords[pos], *normais[pos], u, 1.0 - v])
                origens.append(pos)
            indices.append(mapa[chave])

    return Malha(
        vertices=np.ascontiguousarray(vertices, dtype=np.float32),
        indices=np.ascontiguousarray(indices, dtype=np.uint32),
        posicoes_base=np.ascontiguousarray(coords, dtype=np.float32),
        origens=np.ascontiguousarray(origens, dtype=np.uint32),
        faces_base=np.ascontiguousarray(faces_base, dtype=np.uint32),
    )


def caminho_base_obj() -> Path:
    return Path(__file__).resolve().parents[1] / "codigo" / "makehuman" / "data" / "3dobjs" / "base.obj"
