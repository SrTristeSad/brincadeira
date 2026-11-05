"""Formato experimental de projetos do visualizador Vulkan.

Não utiliza o formato .mhm do MakeHuman original: ele contém regras,
plugins e referências que esta prévia ainda não reproduz integralmente.
O documento JSON registra apenas parâmetros controlados nesta janela.
Versão 2 adicionou dispersão da pele. Versão 3 armazena referências locais
a três texturas PNG em pasta auxiliar, sem caminhos arbitrários.
"""

import json
import math
import os
import hashlib
import re
import struct
from pathlib import Path
import tempfile

from .macro import ETNIAS, VALORES_PADRAO
from .materiais import validar_rgba
from .materiais_obj import escrever_png_rgba


FORMATO = "makehumano-wgpu"
VERSAO = 3
TIPOS_TEXTURAS = ("cor", "normal", "rugosidade")
MAX_DIMENSAO = 4096


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
    versao_origem = documento.get("versao")
    if documento.get("formato") != FORMATO or versao_origem not in (1, 2, VERSAO):
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
    campos_pele = ({"cor", "rugosidade"} if versao_origem == 1
                   else {"cor", "rugosidade", "dispersao"})
    if not isinstance(pele, dict) or set(pele) != campos_pele:
        raise ValueError("Material de pele incompleto")
    cor = pele["cor"]
    if not isinstance(cor, (tuple, list)) or len(cor) != 3:
        raise ValueError("Cor precisa ter três canais RGB")
    rgb = [_numero(valor, 0, 1, "canal RGB") for valor in cor]
    rugosidade = _numero(pele["rugosidade"], 0.05, 1, "rugosidade")
    # O projeto v1 não tinha dispersão: valor zero preserva a imagem antiga.
    dispersao = (0.0 if versao_origem == 1 else
                 _numero(pele["dispersao"], 0, 1, "dispersão"))

    # Versões anteriores não possuíam imagens associadas ao projeto.
    imagens = (documento.get("texturas") if versao_origem == VERSAO
               else {tipo: None for tipo in TIPOS_TEXTURAS})
    if not isinstance(imagens, dict) or set(imagens) != set(TIPOS_TEXTURAS):
        raise ValueError("Referências das texturas incompletas")
    texturas = {}
    for tipo in TIPOS_TEXTURAS:
        nome = imagens[tipo]
        if nome is not None and (
            not isinstance(nome, str)
            or re.fullmatch(rf"{tipo}-[0-9a-f]{{20}}\\.png", nome) is None
        ):
            raise ValueError(f"Arquivo de textura inválido: {tipo}")
        texturas[tipo] = nome

    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "macros": macros,
        "etnias": etnias,
        "modificadores": modificadores,
        "pele": {"cor": rgb, "rugosidade": rugosidade,
                 "dispersao": dispersao},
        "texturas": texturas,
    }


def montar_documento(perfil, modificadores: dict, pele, catalogo) -> dict:
    """Extrai o estado atual sem incluir caminhos de texturas externas."""
    return validar_documento({
        "formato": FORMATO,
        "versao": VERSAO,
        "macros": dict(perfil.valores),
        "etnias": dict(perfil.etnias),
        "modificadores": dict(modificadores),
        "pele": {"cor": list(pele.cor), "rugosidade": pele.rugosidade,
                 "dispersao": pele.dispersao},
        "texturas": {tipo: None for tipo in TIPOS_TEXTURAS},
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


def pasta_texturas(caminho: str | Path) -> Path:
    """Pasta portátil ao lado do JSON: projeto.makehumano.json.assets."""
    return Path(str(Path(caminho)) + ".assets")


def _validar_imagem(pixels, tipo):
    rgba = validar_rgba(pixels)
    altura, largura = rgba.shape[:2]
    if altura > MAX_DIMENSAO or largura > MAX_DIMENSAO:
        raise ValueError(f"Mapa {tipo} maior que {MAX_DIMENSAO} pixels por lado")
    return rgba.copy()


def salvar_projeto_com_texturas(
    caminho: str | Path, documento: dict, catalogo, imagens: dict,
) -> Path:
    """Salva imagens por conteúdo, e publica o JSON somente depois dos PNGs.

    Regravações não excluem PNGs antigos: isso mantém snapshots anteriores
    válidos e evita substituir imagens usadas por outros projetos/versões.
    """
    if not isinstance(imagens, dict) or set(imagens) != set(TIPOS_TEXTURAS):
        raise ValueError("Texturas esperadas: cor, normal e rugosidade")
    destino = Path(caminho)
    doc = validar_documento(documento, catalogo)
    preparados = {}
    for tipo in TIPOS_TEXTURAS:
        pixels = imagens[tipo]
        if pixels is None:
            preparados[tipo] = (None, None)
            continue
        rgba = _validar_imagem(pixels, tipo)
        assinatura = struct.pack(">II", rgba.shape[1], rgba.shape[0])
        digest = hashlib.sha256(assinatura + rgba.tobytes()).hexdigest()[:20]
        nome = f"{tipo}-{digest}.png"
        preparados[tipo] = (nome, rgba)

    pasta = pasta_texturas(destino)
    if any(arr is not None for _, arr in preparados.values()):
        pasta.mkdir(parents=True, exist_ok=True)
    for nome, arr in preparados.values():
        if arr is None:
            continue
        temporario = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=pasta, prefix=".textura-",
                suffix=".tmp", delete=False,
            ) as arquivo:
                temporario = Path(arquivo.name)
            escrever_png_rgba(temporario, arr)
            os.replace(temporario, pasta / nome)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)

    doc["texturas"] = {tipo: preparados[tipo][0] for tipo in TIPOS_TEXTURAS}
    return salvar_documento(destino, doc, catalogo)


def carregar_texturas_projeto(caminho: str | Path, documento: dict, leitor):
    """Carrega as três imagens ANTES de alterar a malha ou a GPU.

    O nome é validado pelo documento v3; não permite caminhos absolutos,
    diretórios pais ou outros nomes arbitrários. `leitor` carrega RGBA8.
    """
    pasta = pasta_texturas(caminho)
    resultado = {}
    for tipo, nome in documento["texturas"].items():
        if nome is None:
            resultado[tipo] = None
            continue
        # Validar também aqui, para não aceitar documentos não validados.
        if re.fullmatch(rf"{tipo}-[0-9a-f]{{20}}\\.png", nome) is None:
            raise ValueError(f"Caminho da textura não permitido: {tipo}")
        arquivo = pasta / nome
        # Arquivos menores que 512 MB; dimensões de pixels também limitadas.
        if arquivo.stat().st_size > 512 * 1024 * 1024:
            raise ValueError("Arquivo de textura muito grande")
        resultado[tipo] = _validar_imagem(leitor(arquivo), tipo)
    return resultado
