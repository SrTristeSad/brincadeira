"""Leitura *parcial* de materiais .mhmat originais para acessórios Vulkan.

MakeHuman Material.fromFile interpreta muitas opções de OpenGL, shaders e
texturas. Este leitor deliberadamente importa só diffuseColor, shininess
(com conversão artística) e diffuseTexture. Qualquer recurso não reproduzido
é relatado; nenhum caminho arbitrário de arquivo ou script é executado.
"""

from dataclasses import dataclass
import math
from pathlib import Path, PurePosixPath
import re


@dataclass(frozen=True)
class MaterialMHMat:
    origem: Path
    cor: tuple[float, float, float]
    rugosidade: float
    textura: Path | None
    avisos: tuple[str, ...]


def _arquivo_local(pasta: Path, nome: str, *, permitir_material_irmao=False) -> Path:
    """Restringe referências à pasta atual ou a ../materials/<arquivo>.

    A organização alternativa é usada por eyes/low-poly/low-poly.mhclo,
    cujo material mora em eyes/materials/brown.mhmat. Não aceita referência
    absoluta, unidade Windows, URLs ou fuga por links simbólicos.
    """
    if not isinstance(nome, str) or not nome or "\\" in nome:
        raise ValueError("Caminho de asset inválido")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", nome):
        raise ValueError("Caminho de asset não pode ser URL ou unidade")
    ref = PurePosixPath(nome)
    if ref.is_absolute() or not nome.endswith((".mhmat", ".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        raise ValueError("Asset precisa ser arquivo local suportado")
    partes = ref.parts
    if any(parte in ("", ".") for parte in partes):
        raise ValueError("Referência local inválida")
    if ".." in partes:
        if not (permitir_material_irmao
                and len(partes) == 3
                and partes[:2] == ("..", "materials")):
            raise ValueError("Caminho externo não autorizado no material")
    limite = pasta.parent.resolve() if ".." in partes else pasta.resolve()
    caminho = (pasta / nome).resolve()
    if not caminho.is_relative_to(limite):
        raise ValueError("Asset escapa da pasta permitida")
    if not caminho.is_file():
        raise FileNotFoundError(f"Asset não encontrado: {nome}")
    return caminho


def _numero(valor: str, chave: str) -> float:
    try:
        numero = float(valor)
    except (ValueError, TypeError) as erro:
        raise ValueError(f"{chave}: valor numérico inválido") from erro
    if not math.isfinite(numero) or not 0.0 <= numero <= 1.0:
        raise ValueError(f"{chave}: esperado valor entre 0 e 1")
    return numero


def material_referenciado(caminho_proxy: str | Path) -> Path | None:
    """Extrai a referência material do cabeçalho de um proxy .mhclo."""
    origem = Path(caminho_proxy)
    nome = None
    with origem.open(encoding="utf-8-sig") as entrada:
        for numero, linha in enumerate(entrada, 1):
            dados = linha.split("#", 1)[0].split()
            if not dados:
                continue
            if dados[0] == "verts":
                break
            if dados[0] == "material":
                if len(dados) != 2 or nome is not None:
                    raise ValueError(f"Linha {numero}: material .mhclo inválido")
                nome = dados[1]
    if nome is None:
        return None
    if not nome.lower().endswith(".mhmat"):
        raise ValueError("O material do proxy precisa usar .mhmat")
    return _arquivo_local(origem.parent, nome, permitir_material_irmao=True)


def carregar_mhmat(caminho: str | Path) -> MaterialMHMat:
    """Interpreta propriedades básicas com avisos para diferenças visuais.

    - diffuseColor: multiplicador RGB de textura, como no material original.
    - shininess: MakeHuman guarda [0,1]; remapeado aproximadamente para
      rugosidade GGX [0.25,1], não uma conversão física.
    - diffuseTexture: imagem local, sem carregamento de arquivos remotos.
    """
    origem = Path(caminho)
    if origem.suffix.lower() != ".mhmat":
        raise ValueError("Material deve ter extensão .mhmat")
    if origem.stat().st_size > 1024 * 1024:
        raise ValueError("Material .mhmat maior que 1 MB")
    cor = (1.0, 1.0, 1.0)
    rugosidade = 0.28
    textura = None
    avisos = set()
    vistos = set()
    with origem.open(encoding="utf-8-sig") as entrada:
        for n, linha in enumerate(entrada, 1):
            partes = linha.split("#", 1)[0].split()
            if not partes:
                continue
            chave, valores = partes[0], partes[1:]
            if chave in {"diffuseColor", "shininess", "diffuseTexture", "opacity"}:
                if chave in vistos:
                    raise ValueError(f"Linha {n}: propriedade duplicada: {chave}")
                vistos.add(chave)
            if chave == "diffuseColor":
                if len(valores) != 3:
                    raise ValueError(f"Linha {n}: diffuseColor precisa de RGB")
                cor = tuple(_numero(v, chave) for v in valores)
            elif chave == "shininess":
                if len(valores) != 1:
                    raise ValueError(f"Linha {n}: shininess inválido")
                valor = _numero(valores[0], chave)
                rugosidade = max(0.05, 1.0 - 0.75 * valor)
                avisos.add("Shininess aproximado por rugosidade GGX")
            elif chave == "diffuseTexture":
                if len(valores) != 1:
                    raise ValueError(f"Linha {n}: diffuseTexture inválida")
                textura = _arquivo_local(origem.parent, valores[0])
            elif chave == "opacity":
                if len(valores) != 1:
                    raise ValueError(f"Linha {n}: opacity inválida")
                if _numero(valores[0], chave) != 1.0:
                    avisos.add("Transparência parcial não implementada no Vulkan")
            elif chave in {"name", "tag", "description", "ambientColor",
                           "specularColor", "emissiveColor", "castShadows",
                           "receiveShadows", "backfaceCull", "alphaToCoverage"}:
                # Propriedades informativas ou do pipeline OpenGL original.
                pass
            elif chave in {"shader", "shaderParam", "shaderConfig",
                           "shadeless", "wireframe", "transparent",
                           "translucency", "depthless", "uvMap",
                           "normalmapTexture", "normalmapIntensity",
                           "bumpmapTexture", "bumpmapIntensity",
                           "specularmapTexture", "specularmapIntensity",
                           "aomapTexture", "aomapIntensity",
                           "displacementmapTexture", "displacementmapIntensity",
                           "sssEnabled", "sssRScale", "sssGScale", "sssBScale",
                           "viewPortColor", "viewPortAlpha",
                           "autoBlendSkin", "transparencymapTexture",
                           "transparencymapIntensity"}:
                avisos.add("Propriedades do shader/material original não reproduzidas")
            else:
                avisos.add(f"Propriedade .mhmat sem suporte: {chave}")
    return MaterialMHMat(
        origem=origem, cor=cor, rugosidade=rugosidade,
        textura=textura, avisos=tuple(sorted(avisos)),
    )
