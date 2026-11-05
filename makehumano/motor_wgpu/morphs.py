"""Aplicação de morph targets originais MakeHuman sem OpenGL nem PyQt.

Os alvos .target armazenam deslocamentos por índice da malha OBJ original.
O renderizador tem vértices duplicados nas costuras UV; portanto as alterações
devem ser aplicadas na malha canônica e só depois propagadas à GPU.
"""

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np

from .malha import Malha, calcular_normais


@dataclass(frozen=True)
class Alvo:
    indices: np.ndarray          # uint32: índices originais do OBJ
    deslocamentos: np.ndarray    # float32 [n,3]


def ler_target(caminho: str | Path, numero_vertices: int) -> Alvo:
    """Lê um arquivo MakeHuman .target (índice + três deslocamentos em unidades OBJ)."""
    caminho = Path(caminho)
    if caminho.suffix.lower() != ".target":
        raise ValueError("Somente arquivos MakeHuman .target são aceitos")

    indices = []
    vetores = []
    with caminho.open(encoding="utf-8") as arquivo:
        for numero_linha, linha in enumerate(arquivo, 1):
            texto = linha.strip()
            if not texto or texto.startswith("#"):
                continue
            partes = texto.split()
            if len(partes) != 4:
                # Compatível com o leitor original, que ignora linhas sem 4 campos.
                continue
            try:
                indice = int(partes[0])
                valores = tuple(float(v) for v in partes[1:])
            except ValueError as erro:
                raise ValueError(f"{caminho}:{numero_linha}: deslocamento inválido") from erro
            if not (0 <= indice < numero_vertices):
                raise ValueError(f"{caminho}:{numero_linha}: índice fora da malha: {indice}")
            if not all(math.isfinite(valor) for valor in valores):
                raise ValueError(f"{caminho}:{numero_linha}: deslocamento não finito")
            indices.append(indice)
            vetores.append(valores)
    return Alvo(
        indices=np.asarray(indices, dtype=np.uint32),
        deslocamentos=np.asarray(vetores, dtype=np.float32).reshape(-1, 3),
    )


class Deformador:
    """Combina pesos sem acumulação progressiva nem perda da posição de repouso.

    Alterar um slider não soma seu efeito ao resultado anterior: cada atualização
    parte da malha base e aplica todos os pesos ativos. Isso impede drift.
    """

    def __init__(self, malha: Malha):
        self.malha = malha
        self.vertices = malha.vertices.copy()
        self._alvos: dict[str, tuple[Alvo, float]] = {}

    def definir_peso(self, nome: str, alvo: Alvo, peso: float) -> np.ndarray:
        """Mantém compatibilidade com sliders individuais."""
        return self.definir_pesos({nome: (alvo, peso)})

    def definir_pesos(self, atualizacoes: dict[str, tuple[Alvo, float]]) -> np.ndarray:
        """Aplica vários pesos atomicamente e reconstrói a malha uma vez.

        Para sliders bidirecionais, atualizar simultaneamente os pesos dos
        dois targets impede frames intermediários incorretos.
        """
        validados = {}
        for nome, (alvo, peso) in atualizacoes.items():
            if not nome:
                raise ValueError("Nome do alvo não pode ser vazio")
            peso = float(peso)
            if not math.isfinite(peso) or not (0.0 <= peso <= 1.0):
                raise ValueError("Peso deve estar entre 0 e 1")
            if np.any(alvo.indices >= len(self.malha.posicoes_base)):
                raise ValueError(f"Target {nome!r} possui índices fora da malha")
            if alvo.deslocamentos.shape != (alvo.indices.size, 3):
                raise ValueError("Formato de deslocamentos inválido")
            if not np.isfinite(alvo.deslocamentos).all():
                raise ValueError("Deslocamentos inválidos")
            validados[nome] = (alvo, peso)

        for nome, (alvo, peso) in validados.items():
            if peso:
                self._alvos[nome] = (alvo, peso)
            else:
                self._alvos.pop(nome, None)
        return self.reconstruir()

    def restaurar(self) -> np.ndarray:
        self._alvos.clear()
        return self.reconstruir()

    def reconstruir(self) -> np.ndarray:
        posicoes = self.malha.posicoes_base.copy()
        for alvo, peso in self._alvos.values():
            np.add.at(posicoes, alvo.indices, alvo.deslocamentos * peso)

        # O mesmo índice OBJ pode aparecer em múltiplos vértices de render
        # devido às costuras UV. Ambos recebem exatamente a mesma posição/normal.
        origens = self.malha.origens
        self.vertices[:, 0:3] = posicoes[origens]
        normais = calcular_normais(posicoes, self.malha.faces_base)
        self.vertices[:, 3:6] = normais[origens]
        # Os canais UV não são alterados.
        return self.vertices


def pasta_targets() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
        / "data" / "targets"
    )
