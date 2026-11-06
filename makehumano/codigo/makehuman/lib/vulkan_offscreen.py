"""Leitura de framebuffers Vulkan, sem OpenGL.

WebGPU exige linhas alinhadas a 256 bytes nas cópias textura->buffer.
A conversão é feita na CPU para devolver RGB no contrato do MakeHuman.
"""

import numpy as np


def bytes_por_linha_alinhados(largura):
    """Stride RGBA/BGRA alinhado a 256 para copy_texture_to_buffer."""
    if not isinstance(largura, (int, np.integer)) or largura <= 0:
        raise ValueError("Largura offscreen deve ser positiva")
    return ((int(largura) * 4 + 255) // 256) * 256


def decodificar_buffer_rgba(dados, largura, altura, formato):
    """Converte buffer de staging alinhado em RGBA uint8 top-down.

    Preserva o canal alfa, inclusive pixels de fundo transparente.
    """
    stride = bytes_por_linha_alinhados(largura)
    if not isinstance(altura, (int, np.integer)) or altura <= 0:
        raise ValueError("Altura offscreen deve ser positiva")
    if formato not in ("rgba8unorm", "rgba8unorm-srgb",
                       "bgra8unorm", "bgra8unorm-srgb"):
        raise ValueError("Formato offscreen incompatível: " + str(formato))
    bruto = np.frombuffer(dados, dtype=np.uint8)
    esperado = stride * int(altura)
    if bruto.size != esperado:
        raise ValueError("Buffer offscreen tem tamanho inválido")
    linhas = bruto.reshape(int(altura), stride)[:, :int(largura) * 4]
    rgba = linhas.reshape(int(altura), int(largura), 4)
    if formato.startswith("bgra"):
        return np.ascontiguousarray(rgba[:, :, [2, 1, 0, 3]])
    return np.ascontiguousarray(rgba)


def decodificar_buffer_rgb(dados, largura, altura, formato):
    """Extrai RGB do mesmo framebuffer, mantendo a ordem dos canais."""
    return np.ascontiguousarray(
        decodificar_buffer_rgba(dados, largura, altura, formato)[:, :, :3]
    )


def mascarar_alfa_rgba(pixels):
    """Converte o alfa de um RGBA renderizado para a Image RGB do MakeHuman."""
    rgba = np.asarray(pixels)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("Máscara Vulkan exige matriz RGBA uint8")
    return np.ascontiguousarray(np.repeat(rgba[:, :, 3:4], 3, axis=2))
