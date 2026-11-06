"""Texturas CPU do MakeHuman original para o backend Vulkan.

Substitui identificadores OpenGL por dados de imagem. A cena Vulkan é
responsável pela criação dos recursos GPU e por invalidar o cache.
"""

import os
import time

import numpy as np

from image import Image
from getpath import getSysDataPath
from core import G
import log


NOTFOUND_TEXTURE = getSysDataPath("textures/texture_notfound.png")
_textureCache = {}


def chave_arquivo(path):
    """Mesma chave para caminhos relativos/absolutos e barras no Windows."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


class Texture:
    """Compatibilidade com a API original sem glGenTextures/glBindTexture."""

    def __init__(self, image=None, size=None, components=4):
        self.textureId = None
        self.width = 0
        self.height = 0
        self.modified = None
        self._data = None
        if image is not None:
            self.loadImage(image)
        elif size is not None:
            self.initTexture(*size, components=components)

    @property
    def data(self):
        return self._data

    @staticmethod
    def getFormat(components):
        if components not in (1, 2, 3, 4):
            raise RuntimeError("Formato de textura não suportado")
        return components

    def initTexture(self, width, height, components=4, pixels=None):
        width, height, components = int(width), int(height), int(components)
        self.getFormat(components)
        if width < 1 or height < 1:
            raise ValueError("Dimensões de textura inválidas")
        if pixels is None:
            matriz = np.zeros((height, width, components), dtype=np.uint8)
        else:
            matriz = np.asarray(pixels, dtype=np.uint8)
            if matriz.size != width * height * components:
                raise ValueError("Número de pixels incompatível")
            matriz = matriz.reshape(height, width, components)
        self._data = np.ascontiguousarray(matriz.copy())
        self.width, self.height = width, height
        self.modified = time.time_ns()
        _invalidar()

    def loadImage(self, image):
        if isinstance(image, str) or isinstance(image, os.PathLike):
            image = Image(path=str(image))
        pixels = np.asarray(image.data, dtype=np.uint8)
        if pixels.ndim != 3 or pixels.shape[2] not in (1, 2, 3, 4):
            raise ValueError("Formato de imagem inválido")
        self._data = np.ascontiguousarray(pixels.copy())
        self.height, self.width = pixels.shape[:2]
        self.modified = time.time_ns()
        _invalidar()

    def loadSubImage(self, image, x, y):
        if self._data is None:
            raise RuntimeError("Textura sem pixels")
        if isinstance(image, str) or isinstance(image, os.PathLike):
            image = Image(path=str(image))
        sub = np.asarray(image.data, dtype=np.uint8)
        x, y = int(x), int(y)
        if sub.ndim != 3 or sub.shape[2] != self._data.shape[2]:
            raise ValueError("Componentes diferentes na subtextura")
        h, w = sub.shape[:2]
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise ValueError("Subtextura fora dos limites")
        self._data[y:y+h, x:x+w] = sub
        self.modified = time.time_ns()
        _invalidar()


def _invalidar(caminho=None):
    canvas = getattr(G, "canvas", None)
    acao = getattr(canvas, "invalidar_texturas", None)
    if callable(acao):
        acao(caminho)


def getTexture(path, cache=None):
    if cache is None:
        cache = _textureCache
    if isinstance(path, Image):
        # A cópia de uma Image é independente do arquivo que a originou.
        # Misturar chaves também misturava versões float de Image com mtime.
        key = ("image", id(path))
        atual = cache.get(key)
        if atual is None:
            atual = Texture(path)
            cache[key] = atual
        elif getattr(path, "modified", None) != getattr(atual, "_source_version", None):
            atual.loadImage(path)
        atual._source_version = getattr(path, "modified", None)
        return atual
    if not isinstance(path, (str, os.PathLike)):
        return None
    path = os.fspath(path)
    if not os.path.isfile(path):
        log.error("Arquivo de textura inexistente: %s", path)
        return None
    stat = os.stat(path)
    mtime = stat.st_mtime_ns
    key = chave_arquivo(path)
    cached = cache.get(key)
    if cached is None:
        cached = Texture(path)
        cache[key] = cached
    elif (getattr(cached, "_source_version", None) != mtime
          or getattr(cached, "_source_size", None) != stat.st_size):
        cached.loadImage(path)
    cached._source_version = mtime
    cached._source_size = stat.st_size
    return cached


def reloadTextures():
    _textureCache.clear()
    _invalidar()


def reloadTexture(path):
    _textureCache.pop(chave_arquivo(path), None)
    _invalidar(path)
