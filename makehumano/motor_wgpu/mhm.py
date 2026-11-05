"""Importação limitada e verificável do formato .mhm original MakeHuman.

A implementação é somente de leitura. O arquivo MHM pode conter plugins,
materiais, roupas, poses, câmera e dados de versões antigas que o visualizador
wgpu NÃO interpreta. Nenhuma informação desconhecida é aplicada
silenciosamente ou executada.

A sintaxe básica foi conferida com Human.load/ Human.save em apps/human.py
e os nomes de modificadores com loadModifiers em apps/humanmodifier.py.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path

from .macro import ETNIAS, PerfilMacro
from .materiais import Pele
from .modificadores import PASTA_MODIFICADORES
from .projetos import montar_documento, validar_documento


@dataclass(frozen=True)
class ImportacaoMHM:
    documento: dict
    avisos: tuple[str, ...]
    modificadores_lidos: int
    modificadores_aplicados: int
    versao_origem: str | None


def _mapa_macros(pasta_modificadores: Path) -> dict[str, tuple[str, str]]:
    """Deriva os nomes MHM do catálogo original, não de uma lista de arquivos."""
    arquivo = Path(pasta_modificadores) / "modeling_modifiers.json"
    blocos = json.loads(arquivo.read_text(encoding="utf-8"))
    controle = set(PerfilMacro().valores)
    resultado = {}
    for grupo in blocos:
        for definicao in grupo["modifiers"]:
            if "macrovar" not in definicao:
                continue
            nome = definicao["macrovar"]
            chave = nome[:1].lower() + nome[1:]
            destino = ("etnia", chave) if chave in ETNIAS else ("macro", chave)
            if destino[0] == "macro" and chave not in controle:
                raise ValueError(f"Macro do MakeHuman ainda sem suporte: {nome}")
            full_name = f'{grupo["group"]}/{nome}'
            if full_name in resultado:
                raise ValueError(f"Definição de macro duplicada: {full_name}")
            resultado[full_name] = destino
    return resultado


def carregar_mhm(
    caminho: str | Path, catalogo,
    *, pasta_modificadores: Path = PASTA_MODIFICADORES,
) -> ImportacaoMHM:
    """Importa somente os parâmetros que têm equivalente comprovado na prévia.

    Sliders originais usam [-1,1] e os da prévia trabalham em inteiros
    [-100,100]. Caso algum valor precise de arredondamento, a perda de
    precisão é informada como aviso. Macrovariáveis mantêm float [0,1].
    As três proporções étnicas são normalizadas exatamente como o estágio
    final de Human.load(): Human._setEthnicVals() sem 'exclude'.
    """
    arquivo = Path(caminho)
    if arquivo.suffix.lower() != ".mhm":
        raise ValueError("Escolha um arquivo MakeHuman .mhm")
    if arquivo.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("O MHM excede o limite de 2 MB da prévia")

    nomes_diretos = {item.identificador: item for item in catalogo}
    nomes_macros = _mapa_macros(pasta_modificadores)
    if set(nomes_diretos) & set(nomes_macros):
        raise ValueError("Identificador repetido entre macros e sliders")

    perfil = PerfilMacro()
    diretos = {}
    vistos = {}
    avisos = []
    lidos = 0
    aplicados = 0
    versao = None
    desconhecidos = set()
    ignorados = set()

    with arquivo.open("r", encoding="utf-8-sig") as entrada:
        for n, linha in enumerate(entrada, 1):
            dados = linha.strip().split()
            if not dados or dados[0].startswith("#"):
                continue
            tipo = dados[0]
            if tipo == "version":
                if len(dados) != 2:
                    raise ValueError(f"Linha {n}: versão MHM inválida")
                versao = dados[1]
            elif tipo == "modifier":
                if len(dados) != 3:
                    raise ValueError(f"Linha {n}: modificador MHM inválido")
                nome = dados[1]
                try:
                    valor = float(dados[2])
                except ValueError as e:
                    raise ValueError(f"Linha {n}: valor não numérico") from e
                if not math.isfinite(valor):
                    raise ValueError(f"Linha {n}: modificador não finito")
                lidos += 1
                if nome not in nomes_diretos and nome not in nomes_macros:
                    desconhecidos.add(nome)
                    continue
                if nome in vistos:
                    avisos.append(f"Modificador {nome} repetido: vale a última linha")
                vistos[nome] = n
                if nome in nomes_diretos:
                    mod = nomes_diretos[nome]
                    minimo = mod.minimo / 100
                    if not minimo <= valor <= 1.0:
                        raise ValueError(f"Linha {n}: valor fora do intervalo para {nome}")
                    inteiro = round(valor * 100)
                    if abs(inteiro / 100 - valor) > 0.00001:
                        avisos.append(f"{nome}: valor arredondado a 1%")
                    if inteiro:
                        diretos[nome] = inteiro
                    else:
                        diretos.pop(nome, None)
                else:
                    if not 0.0 <= valor <= 1.0:
                        raise ValueError(f"Linha {n}: macro fora do intervalo: {nome}")
                    classe, chave = nomes_macros[nome]
                    if classe == "macro":
                        perfil.definir(chave, valor)
                    else:
                        # Human.load bloqueia updates étnicos até ler as linhas.
                        perfil.etnias[chave] = valor
                aplicados += 1
            elif tipo in {"uuid", "name", "tags", "camera", "subdivide"}:
                if tipo in {"camera", "subdivide"}:
                    ignorados.add(tipo)
                # Metadados básicos não influenciam a geometria.
            else:
                ignorados.add(tipo)

    if desconhecidos:
        avisos.append(
            f"{len(desconhecidos)} identificador(es) de modificador sem suporte: "
            + ", ".join(sorted(desconhecidos)[:5])
            + ("…" if len(desconhecidos) > 5 else "")
        )
    if ignorados:
        avisos.append(
            "Propriedades MHM não importadas: " + ", ".join(sorted(ignorados))
        )

    # Equivalente ao pós-carregamento do MakeHuman original:
    # self.blockEthnicUpdates=False; self._setEthnicVals().
    total = sum(perfil.etnias.values())
    if total == 0:
        perfil.etnias = {chave: 1.0 / 3.0 for chave in ETNIAS}
    else:
        perfil.etnias = {
            chave: valor / total for chave, valor in perfil.etnias.items()
        }
    if versao is None:
        avisos.append("Versão MHM ausente: compatibilidade não garantida")
    else:
        # A prévia não executa os conversores compat.loadMHM de versões antigas.
        avisos.append(
            f"Arquivo {versao}: conversões de versões antigas não disponíveis"
        )

    # O .mhm não tem o material WGSL desta prévia. Não reproduzimos um SSS
    # inventado: dispersão zero preserva o comportamento do protótipo anterior.
    doc = montar_documento(
        perfil, diretos, Pele(dispersao=0.0), catalogo
    )
    return ImportacaoMHM(
        documento=validar_documento(doc, catalogo),
        avisos=tuple(avisos),
        modificadores_lidos=lidos,
        modificadores_aplicados=aplicados,
        versao_origem=versao,
    )
