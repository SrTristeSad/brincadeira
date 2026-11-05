"""Snapshots portáteis de acessórios externos para projetos JSON do Vulkan.

Cada peça é armazenada em .assets/acessorios/<hash>/ com proxy.mhclo,
malha.obj e textura.png. O .mhclo é normalizado para referir somente
malha.obj; as referências externas a materiais .mhmat não são preservadas,
pois apenas a aparência RGBA/RGB/rugosidade interpretada é suportada.

Os diretórios são identificados pelo conteúdo. O carregamento verifica hashes
ANTES de criar qualquer acessório na GPU. Não executa scripts, não segue
symlinks nem acessa caminhos descritos no JSON.
"""

import hashlib
import math
import os
from pathlib import Path
import re
import struct
import tempfile

import numpy as np

from .materiais_obj import escrever_png_rgba
from .projetos import _validar_imagem, pasta_texturas
from .roupas import carregar_peca_externa


IDENTIFICADOR = re.compile(r"[0-9a-f]{24}\Z")
MAX_PECAS = 24
MAX_PROXY_BYTES = 64 * 1024 * 1024
MAX_OBJ_BYTES = 64 * 1024 * 1024
MAX_PNG_BYTES = 128 * 1024 * 1024


def _pasta_segura(pasta: Path):
    if pasta.is_symlink():
        raise ValueError("Pasta de recursos não pode ser link simbólico")


def _bytes_seguro(caminho: Path, maximo: int) -> bytes:
    if caminho.is_symlink():
        raise ValueError("Arquivos de projeto não podem ser links simbólicos")
    if caminho.stat().st_size > maximo:
        raise ValueError("Arquivo de acessório muito grande")
    return caminho.read_bytes()


def _proxy_normalizado(proxy: Path) -> tuple[bytes, bytes]:
    """Copia o .mhclo com OBJ local fixo e sem referência a .mhmat externo."""
    bruto = _bytes_seguro(proxy, MAX_PROXY_BYTES)
    texto = bruto.decode("utf-8-sig")
    linhas = []
    nome_obj = None
    for linha in texto.splitlines():
        tokens = linha.split("#", 1)[0].split()
        if tokens and tokens[0] == "obj_file":
            if len(tokens) != 2 or nome_obj is not None:
                raise ValueError("Proxy precisa declarar exatamente um obj_file")
            nome_obj = tokens[1]
            if (Path(nome_obj).name != nome_obj or "\\" in nome_obj
                    or not nome_obj.lower().endswith(".obj")):
                raise ValueError("OBJ externo ou inválido no proxy")
            linhas.append("obj_file malha.obj")
        elif tokens and tokens[0] == "material":
            # Não reabrir nem resolver materiais do computador de origem:
            # a aparência RGBA utilizada na GPU será armazenada diretamente.
            continue
        else:
            linhas.append(linha)
    if nome_obj is None:
        raise ValueError("Proxy não declara arquivo OBJ")
    obj = proxy.parent / nome_obj
    bytes_obj = _bytes_seguro(obj, MAX_OBJ_BYTES)
    return ("\n".join(linhas) + "\n").encode("utf-8"), bytes_obj


def _identidade(proxy: bytes, obj: bytes, pixels: np.ndarray) -> str:
    h = hashlib.sha256()
    for bloco in (proxy, obj,
                  struct.pack(">II", pixels.shape[1], pixels.shape[0]),
                  pixels.tobytes()):
        h.update(struct.pack(">Q", len(bloco)))
        h.update(bloco)
    return h.hexdigest()[:24]


def _gravar_atomicamente(caminho: Path, dados=None, *, imagem=None):
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=caminho.parent, prefix=".acessorio-",
            suffix=".tmp", delete=False,
        ) as saida:
            temporario = Path(saida.name)
            if dados is not None:
                saida.write(dados)
        if imagem is not None:
            escrever_png_rgba(temporario, imagem)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _atributos(item):
    if not isinstance(item, dict) or set(item) != {
        "peca", "pixels", "visivel", "cor", "rugosidade"
    }:
        raise ValueError("Acessório precisa conter peça, pixels e material")
    peca = item["peca"]
    if not hasattr(peca, "origem"):
        raise ValueError("Acessório sem caminho de proxy")
    if not isinstance(item["visivel"], bool):
        raise ValueError("Visibilidade do acessório deve ser booleana")
    cor = item["cor"]
    if not isinstance(cor, (tuple, list)) or len(cor) != 3:
        raise ValueError("Cor do acessório inválida")
    canais = []
    for n in cor:
        if isinstance(n, bool) or not isinstance(n, (float, int)):
            raise ValueError("Cor do acessório inválida")
        n = float(n)
        if not math.isfinite(n) or not 0 <= n <= 1:
            raise ValueError("Cor do acessório inválida")
        canais.append(n)
    r = item["rugosidade"]
    if isinstance(r, bool) or not isinstance(r, (float, int)):
        raise ValueError("Rugosidade do acessório inválida")
    r = float(r)
    if not math.isfinite(r) or not 0.05 <= r <= 1:
        raise ValueError("Rugosidade do acessório inválida")
    return peca, _validar_imagem(item["pixels"], "acessorio"), tuple(canais), r


def salvar_acessorios_projeto(caminho, itens):
    """Escreve recursos e retorna referências JSON, sem publicar o JSON.

    Nenhum acessório anterior é apagado; cópias antigas de projeto podem
    continuar usando seus hashes. O chamador publica o JSON por último.
    """
    itens = list(itens)
    if len(itens) > MAX_PECAS:
        raise ValueError(f"Máximo de {MAX_PECAS} acessórios por projeto")
    preparados = []
    for item in itens:
        peca, pixels, cor, rugosidade = _atributos(item)
        proxy, obj = _proxy_normalizado(Path(peca.origem))
        identificador = _identidade(proxy, obj, pixels)
        preparados.append((identificador, proxy, obj, pixels, cor,
                           rugosidade, item["visivel"]))

    raiz = pasta_texturas(caminho)
    _pasta_segura(raiz)
    pasta_acessorios = raiz / "acessorios"
    _pasta_segura(pasta_acessorios)
    if preparados:
        pasta_acessorios.mkdir(parents=True, exist_ok=True)
    resultado = []
    for ident, proxy, obj, pixels, cor, rugosidade, visivel in preparados:
        pasta = pasta_acessorios / ident
        _pasta_segura(pasta)
        pasta.mkdir(exist_ok=True)
        _gravar_atomicamente(pasta / "proxy.mhclo", proxy)
        _gravar_atomicamente(pasta / "malha.obj", obj)
        _gravar_atomicamente(pasta / "textura.png", imagem=pixels)
        resultado.append({
            "id": ident,
            "visivel": visivel,
            "cor": list(cor),
            "rugosidade": rugosidade,
        })
    return resultado


def carregar_acessorios_projeto(caminho, documento, malha_corpo, leitor):
    """Carrega/valida TODAS as peças antes de modificar o estado da GPU."""
    itens = documento["acessorios"]
    pasta_assets = pasta_texturas(caminho)
    pasta_acessorios = pasta_assets / "acessorios"
    _pasta_segura(pasta_assets)
    _pasta_segura(pasta_acessorios)
    resultado = []
    for item in itens:
        ident = item["id"]
        if IDENTIFICADOR.fullmatch(ident) is None:
            raise ValueError("Identificador de acessório inválido")
        pasta = pasta_acessorios / ident
        _pasta_segura(pasta)
        proxy_caminho = pasta / "proxy.mhclo"
        obj_caminho = pasta / "malha.obj"
        png_caminho = pasta / "textura.png"
        proxy = _bytes_seguro(proxy_caminho, MAX_PROXY_BYTES)
        obj = _bytes_seguro(obj_caminho, MAX_OBJ_BYTES)
        if png_caminho.is_symlink() or png_caminho.stat().st_size > MAX_PNG_BYTES:
            raise ValueError("PNG de acessório inseguro ou muito grande")
        pixels = _validar_imagem(leitor(png_caminho), "acessorio")
        if _identidade(proxy, obj, pixels) != ident:
            raise ValueError("Acessório alterado ou corrompido")
        peca = carregar_peca_externa(proxy_caminho, malha_corpo)
        resultado.append({
            "peca": peca,
            "pixels": pixels,
            "visivel": item["visivel"],
            "cor": tuple(item["cor"]),
            "rugosidade": item["rugosidade"],
        })
    return resultado
