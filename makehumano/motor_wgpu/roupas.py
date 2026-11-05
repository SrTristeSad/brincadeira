"""Entrada explícita de acessórios/roupas .mhclo externos na prévia Vulkan.

Os arquivos de roupa não acompanham o repositório. Esta etapa permite
selecionar um proxy e o OBJ correspondente no disco, sem adivinhar a forma
nem executar plugins/arquivos de material. Apenas 'verts 0' direto (1 campo)
ou ponderado (9 campos) é aceito, utilizando os leitores já testados.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .acessorios import carregar_proxy_direto, carregar_proxy_ponderado
from .malha import Malha


@dataclass(frozen=True)
class PecaExterna:
    origem: Path
    modelo: object
    tipo: str

    @property
    def deletar_vertices(self) -> np.ndarray | None:
        return getattr(self.modelo, "deletar_vertices", None)

    def atualizar(self, posicoes_corpo: np.ndarray) -> np.ndarray:
        return self.modelo.atualizar(posicoes_corpo)


def tipo_referencia_mhclo(caminho: str | Path) -> str:
    """Identifica 1 ou 9 campos na PRIMEIRA linha de vertices do proxy."""
    origem = Path(caminho)
    if origem.suffix.lower() != ".mhclo":
        raise ValueError("Selecione um arquivo .mhclo")
    if origem.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Proxy .mhclo maior que 64 MB")

    encontrou_secao = False
    with origem.open(encoding="utf-8-sig") as arquivo:
        for linha in arquivo:
            dados = linha.split("#", 1)[0].split()
            if not dados:
                continue
            if dados[0] == "verts":
                if encontrou_secao or dados != ["verts", "0"]:
                    raise ValueError("Seção de vértices do proxy não suportada")
                encontrou_secao = True
                continue
            if encontrou_secao:
                if len(dados) == 1:
                    try:
                        int(dados[0])
                    except ValueError as erro:
                        raise ValueError("Referência direta inválida") from erro
                    return "direto"
                if len(dados) == 9:
                    try:
                        for item in dados[:3]:
                            int(item)
                        for item in dados[3:]:
                            float(item)
                    except ValueError as erro:
                        raise ValueError("Referências ponderadas inválidas") from erro
                    return "ponderado"
                raise ValueError(
                    "Apenas referências diretas ou ponderadas são suportadas"
                )
    raise ValueError("Arquivo .mhclo sem vértices de referência")


def carregar_peca_externa(caminho: str | Path, corpo: Malha) -> PecaExterna:
    """Carrega proxy/OBJ locais, revalida índices e só retorna se consistente.

    Uma peça externa deve fornecer OBJ em sua própria pasta. Não é interpretado
    o caminho de plugins, rig, roupa dinâmica ou material .mhmat. Não confunde
    OBJ avulso com arquivo de deformação MakeHuman.
    """
    origem = Path(caminho)
    tipo = tipo_referencia_mhclo(origem)
    modelo = (carregar_proxy_direto(origem, corpo) if tipo == "direto"
              else carregar_proxy_ponderado(origem, corpo))
    # Limitar renderização de arquivos grandes escolhidos pelo usuário.
    if len(modelo.malha.vertices) > 1_000_000:
        raise ValueError("Acessório excede um milhão de vértices renderizados")
    if len(modelo.malha.indices) > 3_000_000:
        raise ValueError("Acessório excede um milhão de triângulos")
    resultado = modelo.atualizar(corpo.posicoes_base)
    if not np.isfinite(resultado).all():
        raise ValueError("Geometria inválida ao carregar acessório")
    return PecaExterna(origem=origem, modelo=modelo, tipo=tipo)
