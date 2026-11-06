"""Texturas de arquivos do piloto Vulkan na viewport ORIGINAL do MakeHuman.

O motor OpenGL legado invalida o cache quando um arquivo de textura muda.
A ponte Vulkan deve fazer o mesmo, inclusive quando o arquivo aparece depois
de uma primeira tentativa de carregamento malsucedida.

Este módulo não importa OpenGL nem cria um editor ou formato novo.
"""

import os

import numpy as np


def assinatura_arquivo(caminho):
    """Identifica versões de um arquivo sem ler ou decodificar a imagem.

    Além da data e tamanho, dispositivo/inode/ctime detectam substituições
    atômicas de arquivo com mtime e tamanho preservados.
    """
    if not caminho:
        return None
    try:
        stat = os.stat(caminho)
    except OSError:
        return None
    if not os.path.isfile(caminho):
        return None
    return (stat.st_dev, stat.st_ino, stat.st_size,
            stat.st_mtime_ns, stat.st_ctime_ns)


class CacheTexturasVulkan:
    """Cache de textura GPU por caminho e versão do arquivo no disco."""

    def __init__(self, device, wgpu, QtGui):
        self.device = device
        self.wgpu = wgpu
        self.QtGui = QtGui
        self._entradas = {}

    def obter(self, caminho):
        chave = str(caminho or "")
        assinatura = assinatura_arquivo(chave)
        anterior = self._entradas.get(chave)
        if anterior is not None and anterior[0] == assinatura:
            return anterior[1]

        # Imagem ausente/inválida: mantém o branco neutro anterior.
        # Quando um arquivo surgir ou mudar, sua assinatura mudará também.
        imagem = self.QtGui.QImage(chave) if assinatura else self.QtGui.QImage()
        if imagem.isNull():
            pixels = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
        else:
            imagem = imagem.convertToFormat(self.QtGui.QImage.Format_RGBA8888)
            largura, altura = imagem.width(), imagem.height()
            pixels = np.frombuffer(
                imagem.bits().asstring(largura * altura * 4),
                dtype=np.uint8,
            ).reshape((altura, largura, 4)).copy()

        altura, largura = pixels.shape[:2]
        textura = self.device.create_texture(
            size=(largura, altura, 1),
            dimension="2d",
            format="rgba8unorm",
            usage=(self.wgpu.TextureUsage.TEXTURE_BINDING
                   | self.wgpu.TextureUsage.COPY_DST),
        )
        self.device.queue.write_texture(
            self.wgpu.TexelCopyTextureInfo(
                texture=textura, mip_level=0, origin=(0, 0, 0)
            ),
            pixels.tobytes(),
            self.wgpu.TexelCopyBufferLayout(
                offset=0, bytes_per_row=largura * 4, rows_per_image=altura
            ),
            (largura, altura, 1),
        )
        self._entradas[chave] = (assinatura, textura)
        return textura
