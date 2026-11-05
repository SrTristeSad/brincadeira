"""Máscaras de vértices e triângulos para acessórios/roupas MakeHuman.

Os índices dos triângulos mantêm a numeração UV original. A máscara atua
somente no index buffer; não edita a malha base, os morph targets ou UVs.
"""

import numpy as np

from .malha import Malha


def indices_corpo_visiveis(malha: Malha, deletar_vertices) -> np.ndarray:
    """Filtra faces com qualquer vértice canônico marcado para ocultação."""
    apagados = np.asarray(deletar_vertices)
    if apagados.dtype != np.bool_ or apagados.shape != (len(malha.posicoes_base),):
        raise ValueError("Máscara deve ser booleana por vértice canônico")
    if np.asarray(malha.indices).size % 3:
        raise ValueError("Índices da malha não formam triângulos")
    faces = np.asarray(malha.indices).reshape(-1, 3)
    if np.any(faces >= len(malha.origens)):
        raise ValueError("Face referencia vértice inexistente")
    originais = malha.origens[faces]
    manter = ~np.any(apagados[originais], axis=1)
    return np.ascontiguousarray(faces[manter].ravel(), dtype=np.uint32)


def transferir_mascara_proxy(visivel_corpo, referencias, pesos) -> np.ndarray:
    """Mesmo critério de shared/proxy.py:transferVertexMaskToProxy().

    Com pesos só na primeira referência, usa aquela referência. Em outros
    vértices, exige ao menos duas das três referências visíveis; os pesos
    são interpretados como no código original, sem limiar arbitrário.
    """
    visiveis = np.asarray(visivel_corpo)
    refs = np.asarray(referencias)
    ws = np.asarray(pesos)
    if visiveis.dtype != np.bool_ or visiveis.ndim != 1:
        raise ValueError("Visibilidade deve ser vetor booleano")
    if refs.ndim != 2 or refs.shape[1] != 3 or ws.shape != refs.shape:
        raise ValueError("Referências e pesos devem ter formato [n,3]")
    if np.any(refs < 0) or np.any(refs >= len(visiveis)) or not np.isfinite(ws).all():
        raise ValueError("Referência fora do corpo ou pesos inválidos")
    exatos = ~np.any(ws[:, 1:], axis=1)
    visibilidade_ref = visiveis[refs]
    resultado = np.sum(visibilidade_ref.astype(np.uint8), axis=1) >= 2
    resultado[exatos] = visibilidade_ref[exatos, 0]
    return np.ascontiguousarray(resultado, dtype=bool)


class GerenciadorMascaras:
    """Une delete_verts dos acessórios visíveis sem alterar o OBJ original.

    Cada máscara representa índices CANÔNICOS do corpo; mudar visibilidade
    não apaga a máscara armazenada. Uma peça oculta deixa de mascarar o corpo,
    e várias peças visíveis compõem suas máscaras por OU lógico.
    """

    def __init__(self, quantidade_vertices: int):
        if not isinstance(quantidade_vertices, int) or quantidade_vertices < 1:
            raise ValueError("Quantidade de vértices inválida")
        self.quantidade_vertices = quantidade_vertices
        self._mascaras = {}
        self._visibilidade = {}

    def _validar_mascara(self, mascara) -> np.ndarray:
        if mascara is None:
            return np.zeros(self.quantidade_vertices, dtype=bool)
        dados = np.asarray(mascara)
        if (dados.dtype != np.bool_
                or dados.shape != (self.quantidade_vertices,)):
            raise ValueError(
                "delete_verts deve ser máscara booleana por vértice original"
            )
        return np.ascontiguousarray(dados.copy())

    def registrar(self, nome: str, mascara=None, *, visivel=True):
        if not isinstance(nome, str) or not nome or nome in self._mascaras:
            raise ValueError("Nome de acessório vazio ou duplicado")
        validada = self._validar_mascara(mascara)
        self._mascaras[nome] = validada
        self._visibilidade[nome] = bool(visivel)

    def definir_mascara(self, nome: str, mascara=None):
        if nome not in self._mascaras:
            raise KeyError(nome)
        self._mascaras[nome] = self._validar_mascara(mascara)

    def definir_visibilidade(self, nome: str, visivel: bool):
        if nome not in self._mascaras:
            raise KeyError(nome)
        self._visibilidade[nome] = bool(visivel)

    def remover(self, nome: str):
        del self._mascaras[nome]
        del self._visibilidade[nome]

    def combinada(self) -> np.ndarray:
        resultado = np.zeros(self.quantidade_vertices, dtype=bool)
        for nome, mascara in self._mascaras.items():
            if self._visibilidade[nome]:
                resultado |= mascara
        return resultado
