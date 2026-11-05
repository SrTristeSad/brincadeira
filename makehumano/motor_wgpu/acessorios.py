"""Primeiro acessório adaptável: olhos low-poly oficiais do MakeHuman.

As roupas completas ainda não estão no repositório. Os olhos funcionam como
prova de arquitetura: uma malha OBJ separada, UVs próprios, textura própria
e mapeamento de vértices via .mhclo para seguir os morphs do corpo.

Suporta referências diretas e proxies com pesos de três vértices, offsets
e escala diagonal de x/y/z. Shear, máscaras, rig e proxies de roupas completos
permanecem fora do escopo.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .malha import Malha, calcular_normais, carregar_obj
from .transformacoes_proxy import matriz_cisalhamento


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



@dataclass
class AcessorioPonderado:
    """Proxy .mhclo com três referências, pesos e offsets por vértice."""

    malha: Malha
    referencias: np.ndarray     # [n,3] uint32, índices do OBJ base
    pesos: np.ndarray           # [n,3] float32, pesos do .mhclo
    deslocamentos: np.ndarray   # [n,3] float32, offsets antes da escala
    escalas: tuple | None        # três tuplas (v0, v1, denominador)
    nome: str
    textura: Path
    cisalhamento: tuple | None = None
    deletar_vertices: np.ndarray | None = None

    def atualizar(self, posicoes_corpo: np.ndarray) -> np.ndarray:
        """Reproduz Proxy.getCoords + TMatrix.getMatrix com scaleData.

        Os deslocamentos se transformam conforme as dimensões atuais do
        corpo. Os pesos do .mhclo são usados literalmente (sem normalizar).
        """
        corpo = np.asarray(posicoes_corpo, dtype=np.float32)
        if corpo.ndim != 2 or corpo.shape[1] != 3 or not np.isfinite(corpo).all():
            raise ValueError("Coordenadas do corpo precisam ter formato [n,3] finito")
        numero = len(self.malha.posicoes_base)
        if (self.referencias.shape != (numero, 3)
                or self.pesos.shape != (numero, 3)
                or self.deslocamentos.shape != (numero, 3)
                or np.any(self.referencias >= len(corpo))
                or not np.isfinite(self.pesos).all()
                or not np.isfinite(self.deslocamentos).all()):
            raise ValueError("Dados do proxy ponderado inválidos")

        if self.escalas is not None:
            fatores = np.empty(3, dtype=np.float32)
            for eixo, (i, j, denominador) in enumerate(self.escalas):
                if (i >= len(corpo) or j >= len(corpo)
                        or not np.isfinite(denominador) or denominador <= 0):
                    raise ValueError("Referências de escala inválidas no .mhclo")
                fatores[eixo] = abs(
                    float(corpo[i, eixo]) - float(corpo[j, eixo])
                ) / denominador
            offsets = self.deslocamentos * fatores[None, :]
        elif self.cisalhamento is not None:
            matrix = matriz_cisalhamento(self.cisalhamento, corpo)
            offsets = self.deslocamentos @ matrix.T
        else:
            raise ValueError("Proxy sem escala ou shear")

        # Produto de Proxy.getCoords: média ponderada + M @ offset.
        coordenadas = (
            np.sum(corpo[self.referencias] * self.pesos[..., None], axis=1)
            + offsets
        ).astype(np.float32)
        if not np.isfinite(coordenadas).all():
            raise ValueError("Proxy gerou coordenadas não finitas")

        resultado = self.malha.vertices.copy()
        normais = calcular_normais(coordenadas, self.malha.faces_base)
        resultado[:, :3] = coordenadas[self.malha.origens]
        resultado[:, 3:6] = normais[self.malha.origens]
        return resultado


def carregar_proxy_ponderado(
    caminho_mhclo: str | Path, corpo: Malha,
) -> AcessorioPonderado:
    """Aceita .mhclo com 'verts 0', 9 campos e escala x/y/z.

    Outros tipos de proxy (shear, rig, máscara, animação) ainda não são
    interpretados. Evita aplicar offsets com matriz inventada.
    """
    arquivo = Path(caminho_mhclo)
    obj = None
    referencias, pesos, deslocamentos = [], [], []
    escalas = {}
    shears = {"shear": {}, "l_shear": {}, "r_shear": {}}
    deletados = np.zeros(len(corpo.posicoes_base), dtype=bool)
    em_delete = False
    em_vertices = False
    with arquivo.open(encoding="utf-8") as entrada:
        for numero, linha in enumerate(entrada, 1):
            dados = linha.split("#", 1)[0].split()
            if not dados:
                continue
            campo = dados[0]
            if campo == "obj_file":
                if (
                    len(dados) != 2 or Path(dados[1]).name != dados[1]
                    or "\\" in dados[1] or not dados[1].endswith(".obj")
                ):
                    raise ValueError("obj_file precisa apontar a OBJ local")
                obj = arquivo.parent / dados[1]
            elif campo in {"x_scale", "y_scale", "z_scale"}:
                if len(dados) != 4 or campo in escalas:
                    raise ValueError(f"Linha {numero}: escala duplicada ou inválida")
                try:
                    i, j = int(dados[1]), int(dados[2])
                    denominador = float(dados[3])
                except ValueError as erro:
                    raise ValueError(f"Linha {numero}: escala inválida") from erro
                if not (0 <= i < len(corpo.posicoes_base)
                        and 0 <= j < len(corpo.posicoes_base)
                        and np.isfinite(denominador) and denominador > 0):
                    raise ValueError(f"Linha {numero}: escala fora dos limites")
                escalas[campo] = (i, j, denominador)
            elif campo in {
                "shear_x", "shear_y", "shear_z",
                "l_shear_x", "l_shear_y", "l_shear_z",
                "r_shear_x", "r_shear_y", "r_shear_z",
            }:
                partes = campo.rsplit("_", 1)
                familia, eixo = partes
                if em_vertices or em_delete or len(dados) != 5:
                    raise ValueError(f"Linha {numero}: shear inválido")
                if eixo in shears[familia]:
                    raise ValueError(f"Linha {numero}: shear duplicado")
                try:
                    a, b = int(dados[1]), int(dados[2])
                    u, v = float(dados[3]), float(dados[4])
                except ValueError as erro:
                    raise ValueError(f"Linha {numero}: shear inválido") from erro
                if (not 0 <= a < len(corpo.posicoes_base)
                        or not 0 <= b < len(corpo.posicoes_base)
                        or not np.isfinite(u) or not np.isfinite(v)
                        or abs(v - u) < 1e-8):
                    raise ValueError(f"Linha {numero}: shear fora dos limites")
                shears[familia][eixo] = (a, b, u, v)
            elif campo == "verts":
                if len(dados) != 2 or dados[1] != "0" or em_vertices or em_delete:
                    raise ValueError("Somente seção 'verts 0' única é suportada")
                em_vertices = True
            elif campo == "delete_verts":
                if len(dados) != 1 or em_delete:
                    raise ValueError(f"Linha {numero}: delete_verts inválido")
                em_vertices = False
                em_delete = True
            elif em_delete:
                # Sintaxe oficial: índices separados por espaço; 'a - b'
                # inclui o intervalo entre os dois vértices.
                anterior = None
                intervalo = False
                for item in dados:
                    if item == "-":
                        if anterior is None or intervalo:
                            raise ValueError(f"Linha {numero}: intervalo inválido")
                        intervalo = True
                        continue
                    try:
                        indice = int(item)
                    except ValueError as erro:
                        raise ValueError(f"Linha {numero}: máscara inválida") from erro
                    if indice < 0 or indice >= len(deletados):
                        raise ValueError(f"Linha {numero}: índice fora do corpo")
                    if intervalo:
                        if indice < anterior:
                            raise ValueError(f"Linha {numero}: intervalo invertido")
                        deletados[anterior:indice + 1] = True
                        intervalo = False
                    else:
                        deletados[indice] = True
                    anterior = indice
                if intervalo:
                    raise ValueError(f"Linha {numero}: intervalo incompleto")
            elif em_vertices:
                if len(dados) != 9:
                    raise ValueError(
                        f"Linha {numero}: esperado proxy com três referências, "
                        "três pesos e três offsets"
                    )
                try:
                    ref = tuple(int(d) for d in dados[:3])
                    nums = tuple(float(d) for d in dados[3:])
                except ValueError as erro:
                    raise ValueError(f"Linha {numero}: linha de proxy inválida") from erro
                if any(v < 0 or v >= len(corpo.posicoes_base) for v in ref):
                    raise ValueError(f"Linha {numero}: referência fora do corpo")
                if not all(np.isfinite(v) for v in nums):
                    raise ValueError(f"Linha {numero}: peso ou offset não finito")
                referencias.append(ref)
                pesos.append(nums[:3])
                deslocamentos.append(nums[3:])
            elif campo in {
                "uuid", "basemesh", "name", "tag", "z_depth", "material",
            }:
                # Metadados reconhecidos, não afetam o cálculo das posições.
                # Usamos a textura oficial conhecida em vez de resolver um
                # caminho de material arbitrário declarado no .mhclo.
                if em_vertices:
                    raise ValueError(
                        f"Linha {numero}: diretiva após a lista de vértices"
                    )
            else:
                raise ValueError(
                    f"Linha {numero}: seção {campo} não suportada"
                )

    if obj is None or not em_vertices:
        raise ValueError("Proxy sem OBJ ou seção de vértices")
    completos = {"x_scale", "y_scale", "z_scale"}
    if escalas and set(escalas) != completos:
        raise ValueError("Proxy possui escalas x/y/z incompletas")
    usados = tuple(
        familia for familia in ("shear", "l_shear", "r_shear")
        if shears[familia]
    )
    if not escalas and not usados:
        raise ValueError("Proxy ponderado precisa de escala ou shear")
    if any(set(shears[familia]) != {"x", "y", "z"} for familia in usados):
        raise ValueError("Proxy possui shear x/y/z incompleto")
    # Prioridade idêntica a TMatrix.getMatrix: scale, shear, l_shear, r_shear.
    ativo = usados[0] if usados else None
    entrada_shear = (
        tuple(shears[ativo][eixo] for eixo in ("x", "y", "z"))
        if ativo is not None else None
    )
    malha = carregar_obj(obj, grupo=None)
    if len(referencias) != len(malha.posicoes_base):
        raise ValueError("Número de referências não corresponde ao OBJ")

    return AcessorioPonderado(
        malha=malha,
        referencias=np.ascontiguousarray(referencias, dtype=np.uint32),
        pesos=np.ascontiguousarray(pesos, dtype=np.float32),
        deslocamentos=np.ascontiguousarray(deslocamentos, dtype=np.float32),
        escalas=(tuple(escalas[chave] for chave in
                       ("x_scale", "y_scale", "z_scale"))
                 if escalas else None),
        nome=obj.stem,
        textura=arquivo.parent.parent / "materials" / "brown_eye.png",
        cisalhamento=entrada_shear,
        deletar_vertices=deletados,
    )


def caminho_olhos_highpoly() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
        / "data" / "eyes" / "high-poly" / "high-poly.mhclo"
    )


def caminho_olhos_lowpoly() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
        / "data" / "eyes" / "low-poly" / "low-poly.mhclo"
    )
