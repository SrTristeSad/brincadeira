"""Formato experimental de projetos do visualizador Vulkan.

Não utiliza o formato .mhm do MakeHuman original: ele contém regras,
plugins e referências que esta prévia ainda não reproduz integralmente.
O documento JSON registra apenas parâmetros controlados nesta janela.
"""

import json
import math
import os
from pathlib import Path
import tempfile

from .macro import ETNIAS, VALORES_PADRAO


FORMATO = "makehumano-wgpu"
VERSAO = 1


def _numero(valor, menor, maior, campo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{campo}: esperado número")
    numero = float(valor)
    if not math.isfinite(numero) or not menor <= numero <= maior:
        raise ValueError(f"{campo}: valor fora do intervalo [{menor}, {maior}]")
    return numero


def validar_documento(documento: dict, catalogo) -> dict:
    """Valida o documento inteiro ANTES de modificar os controles ou a GPU."""
    if not isinstance(documento, dict):
        raise ValueError("O projeto precisa ser um objeto JSON")
    if documento.get("formato") != FORMATO or documento.get("versao") != VERSAO:
        raise ValueError("Formato ou versão de projeto desconhecidos")

    macros = documento.get("macros")
    if not isinstance(macros, dict) or set(macros) != set(VALORES_PADRAO):
        raise ValueError("Parâmetros gerais ausentes ou desconhecidos")
    macros = {
        chave: _numero(macros[chave], 0, 1, f"macro {chave}")
        for chave in VALORES_PADRAO
    }

    etnias = documento.get("etnias")
    if not isinstance(etnias, dict) or set(etnias) != set(ETNIAS):
        raise ValueError("Misturas herdadas ausentes ou desconhecidas")
    etnias = {nome: _numero(etnias[nome], 0, 1, f"mistura {nome}") for nome in ETNIAS}
    if not math.isclose(sum(etnias.values()), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError("As três misturas precisam somar 100%")

    alteracoes = documento.get("modificadores")
    if not isinstance(alteracoes, dict):
        raise ValueError("Modificadores precisam ser um objeto")
    disponiveis = {mod.identificador: mod for mod in catalogo}
    if set(alteracoes) - set(disponiveis):
        raise ValueError("O projeto contém modificadores desconhecidos")
    modificadores = {}
    for nome, valor in alteracoes.items():
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError(f"Modificador {nome} precisa de valor inteiro")
        if not disponiveis[nome].minimo <= valor <= 100:
            raise ValueError(f"Modificador {nome} fora do intervalo")
        if valor:
            modificadores[nome] = valor

    pele = documento.get("pele")
    if not isinstance(pele, dict) or set(pele) != {"cor", "rugosidade"}:
        raise ValueError("Material de pele incompleto")
    cor = pele["cor"]
    if not isinstance(cor, (tuple, list)) or len(cor) != 3:
        raise ValueError("Cor precisa ter três canais RGB")
    rgb = [_numero(valor, 0, 1, "canal RGB") for valor in cor]
    rugosidade = _numero(pele["rugosidade"], 0.05, 1, "rugosidade")

    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "macros": macros,
        "etnias": etnias,
        "modificadores": modificadores,
        "pele": {"cor": rgb, "rugosidade": rugosidade},
    }


def montar_documento(perfil, modificadores: dict, pele, catalogo) -> dict:
    """Extrai o estado atual sem incluir caminhos de texturas externas."""
    return validar_documento({
        "formato": FORMATO,
        "versao": VERSAO,
        "macros": dict(perfil.valores),
        "etnias": dict(perfil.etnias),
        "modificadores": dict(modificadores),
        "pele": {"cor": list(pele.cor), "rugosidade": pele.rugosidade},
    }, catalogo)


def salvar_documento(caminho: str | Path, documento: dict, catalogo) -> Path:
    destino = Path(caminho)
    validado = validar_documento(documento, catalogo)
    # Gravação atômica protege contra perda se o programa fechar durante o save.
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destino.parent, prefix=".makehumano-",
            suffix=".tmp", delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(validado, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
            arquivo.write("\n")
        os.replace(temporario, destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return destino


def carregar_documento(caminho: str | Path, catalogo) -> dict:
    origem = Path(caminho)
    if origem.stat().st_size > 1024 * 1024:
        raise ValueError("Projeto maior que 1 MB: formato inesperado")
    texto = origem.read_text(encoding="utf-8")
    return validar_documento(json.loads(texto), catalogo)
