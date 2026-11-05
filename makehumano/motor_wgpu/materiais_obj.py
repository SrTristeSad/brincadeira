"""Arquivos de material Wavefront e textura PNG da prévia wgpu.

Implementação PNG RGBA8 com stdlib para que a exportação geométrica
continue independente de Qt, Pillow, Vulkan e da disponibilidade da GPU.
OBJ/MTL é uma aproximação visual do shader WGSL, não um exportador PBR.
"""

import hashlib
from pathlib import Path
import re
import struct
import zlib

import numpy as np

from .materiais import Pele, validar_rgba, textura_neutra


NOME_MATERIAL = "PeleMakeHumano"
ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"


def caminhos_materiais(destino: str | Path) -> tuple[Path, Path]:
    """Retorna MTL e PNG ao lado do OBJ, com nomes portáveis e previsíveis."""
    destino = Path(destino)
    if destino.suffix.lower() != ".obj":
        raise ValueError("O destino precisa terminar em .obj")
    nome = re.sub(r"[^A-Za-z0-9_-]+", "_", destino.stem).strip("_")[:64] or "personagem"
    # Distingue nomes com espaços/acentos que resultariam no mesmo nome seguro.
    if nome != destino.stem:
        sufixo = hashlib.sha256(destino.name.encode("utf-8")).hexdigest()[:8]
        nome += "_" + sufixo
    return destino.with_name(nome + "_pele.mtl"), destino.with_name(nome + "_pele.png")


def caminhos_mapas(destino: str | Path) -> tuple[Path, Path]:
    """Mapas auxiliares do material; MTL não os referencia (sem padrão PBR)."""
    _, png_cor = caminhos_materiais(destino)
    return (
        png_cor.with_name(png_cor.stem + "_normal.png"),
        png_cor.with_name(png_cor.stem + "_rugosidade.png"),
    )


def validar_material(pele: Pele, pixels=None) -> np.ndarray:
    if not isinstance(pele, Pele):
        raise ValueError("Material deve ser do tipo Pele")
    # A dataclass é editável: revalidar antes de gerar arquivos.
    Pele(cor=pele.cor, rugosidade=pele.rugosidade)
    rgba = validar_rgba(textura_neutra() if pixels is None else pixels)
    h, w, _ = rgba.shape
    if h > 8192 or w > 8192:
        raise ValueError("Textura acima do limite de 8192 pixels por dimensão")
    return rgba


def _bloco_png(tipo: bytes, dados: bytes) -> bytes:
    cabecalho = struct.pack(">I", len(dados)) + tipo
    checksum = zlib.crc32(tipo + dados) & 0xFFFFFFFF
    return cabecalho + dados + struct.pack(">I", checksum)


def escrever_png_rgba(caminho: str | Path, pixels) -> None:
    rgba = validar_rgba(pixels)
    h, w, _ = rgba.shape
    if h > 8192 or w > 8192:
        raise ValueError("Textura acima do limite de 8192 pixels por dimensão")
    with Path(caminho).open("wb") as arquivo:
        arquivo.write(ASSINATURA_PNG)
        arquivo.write(_bloco_png(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        compressor = zlib.compressobj(level=6)
        for linha in rgba:
            # Filtro PNG 0: pixels copiados sem alteração, da esquerda à direita.
            bloco = compressor.compress(b"\x00" + linha.tobytes())
            if bloco:
                arquivo.write(_bloco_png(b"IDAT", bloco))
        final = compressor.flush()
        if final:
            arquivo.write(_bloco_png(b"IDAT", final))
        arquivo.write(_bloco_png(b"IEND", b""))


def texto_mtl(pele: Pele, textura_nome: str) -> str:
    """Converte o material WGSL em parâmetros MTL aproximados.

    Kd multiplica os pixels RGB do map_Kd, como o tint do shader. A rugosidade
    GGX não tem equivalência exata em Ns do modelo Phong: é uma aproximação.
    """
    if not isinstance(pele, Pele):
        raise ValueError("Material deve ser do tipo Pele")
    Pele(cor=pele.cor, rugosidade=pele.rugosidade)
    if not textura_nome or "/" in textura_nome or "\\" in textura_nome or any(
        c in textura_nome for c in "\r\n"
    ):
        raise ValueError("Nome da textura inválido para MTL")
    r, g, b = pele.cor
    rough = pele.rugosidade
    ns = max(0.0, min(1000.0, 2.0 / (rough ** 4) - 2.0))
    return (
        "# MakeHumano: material de pele aproximado em Wavefront MTL\n"
        "# Ns aproxima o GGX, sem SSS, normal map ou mapa de rugosidade.\n"
        f"newmtl {NOME_MATERIAL}\n"
        f"Kd {r:.6f} {g:.6f} {b:.6f}\n"
        "Ka 0.000000 0.000000 0.000000\n"
        "Ks 0.035000 0.035000 0.035000\n"
        f"Ns {ns:.6f}\n"
        "d 1.0\n"
        "illum 2\n"
        f"map_Kd {textura_nome}\n"
    )
