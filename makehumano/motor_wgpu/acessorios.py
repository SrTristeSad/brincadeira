"""Primeiro acessório adaptável: olhos low-poly oficiais do MakeHuman.

As roupas completas ainda não estão no repositório. Os olhos funcionam como
prova de arquitetura: uma malha OBJ separada, UVs próprios, textura própria
e mapeamento de vértices via .mhclo para seguir os morphs do corpo.

Implementa somente proxies .mhclo com referências diretas (uma por vértice).
Arquivos com interpolação baricêntrica, offsets ou transformação são rejeitados
explicitamente; não se tenta encaixar roupas complexas de forma incorreta.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .malha import Malha, calcular_normais, carregar_obj


@dataclass
class AcessorioDireto:
    malha: Malha
    referencias: np.ndarray   # [n] índices canônicos do corpo
    nome: str
    textura: Path

    def atualizar(self, posicoes_corpo: np.ndarray) -> np.ndarray:
        """Propaga as coordenadas canônicas deformadas preservando as UVs."""
        corpo = np.asarray(posicoes_corpo, dtype=np.float32)
        if corpo.ndim != 2 or corpo.shape[1] != 3:
            raise ValueError("Coordenadas do corpo devem ter formato [n,3]")
        if self.referencias.size != self.malha.posicoes_base.shape[0]:
            raise ValueError("Número de referências do proxy não corresponde ao OBJ")
        if np.any(self.referencias >= len(corpo)):
            raise ValueError("Proxy contém referência fora do corpo")
        novas_posicoes = np.ascontiguousarray(corpo[self.referencias])
        if not np.isfinite(novas_posicoes).all():
            raise ValueError("A malha deformada contém coordenadas inválidas")
        normais = calcular_normais(novas_posicoes, self.malha.faces_base)
        resultado = self.malha.vertices.copy()
        resultado[:, :3] = novas_posicoes[self.malha.origens]
        resultado[:, 3:6] = normais[self.malha.origens]
        return resultado


def carregar_proxy_direto(caminho_mhclo: str | Path, corpo: Malha) -> AcessorioDireto:
    """Lê OBJ e mapeamento .mhclo de um acessório com vértices diretos."""
    arquivo = Path(caminho_mhclo)
    obj = None
    material = None
    referencias = []
    em_vertices = False
    encontrou_vertices = False
    with arquivo.open(encoding="utf-8") as entrada:
        for numero, linha in enumerate(entrada, 1):
            dados = linha.split("#", 1)[0].split()
            if not dados:
                continue
            if dados[0] == "obj_file":
                if len(dados) != 2 or Path(dados[1]).name != dados[1]:
                    raise ValueError("obj_file deve apontar para OBJ local")
                obj = arquivo.parent / dados[1]
                em_vertices = False
            elif dados[0] == "material":
                # Este primeiro acessório usa a textura oficial selecionada
                # separadamente. Não interpretamos materiais arbitrários.
                material = dados[1] if len(dados) == 2 else None
            elif dados[0] == "verts":
                if len(dados) != 2 or dados[1] != "0":
                    raise ValueError("Somente .mhclo com 'verts 0' é suportado")
                em_vertices = True
                encontrou_vertices = True
            elif em_vertices:
                if len(dados) != 1:
                    raise ValueError(
                        f"Linha {numero}: proxy interpolado não suportado"
                    )
                try:
                    referencia = int(dados[0])
                except ValueError as erro:
                    raise ValueError(
                        f"Linha {numero}: referência de vértice inválida"
                    ) from erro
                if not 0 <= referencia < len(corpo.posicoes_base):
                    raise ValueError(f"Linha {numero}: referência fora do corpo")
                referencias.append(referencia)

    if obj is None or not encontrou_vertices:
        raise ValueError("Acessório .mhclo sem OBJ ou referências")
    malha = carregar_obj(obj, grupo=None)
    refs = np.asarray(referencias, dtype=np.uint32)
    if refs.shape != (len(malha.posicoes_base),):
        raise ValueError("O número de referências não corresponde ao OBJ")

    # Validar correspondência na pose neutra para evitar um acessório
    # deslocado quando o .mhclo e o .obj forem de malhas diferentes.
    if not np.allclose(
        malha.posicoes_base, corpo.posicoes_base[refs],
        atol=0.0002, rtol=0,
    ):
        raise ValueError("A geometria do OBJ não coincide com as referências")

    return AcessorioDireto(
        malha=malha, referencias=refs,
        nome=obj.stem, textura=arquivo.parent.parent / "materials" / "brown_eye.png",
    )


def caminho_olhos_lowpoly() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
        / "data" / "eyes" / "low-poly" / "low-poly.mhclo"
    )
