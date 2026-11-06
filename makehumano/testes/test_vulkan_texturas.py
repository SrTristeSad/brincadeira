"""Regressões das texturas usadas pelo MakeHuman original em Vulkan.

Os testes usam um leitor Qt simulado e uma GPU simulada: verificam a
invalidação de arquivos sem depender de contexto gráfico/OpenGL.
"""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))

from vulkan_texturas import CacheTexturasVulkan, assinatura_arquivo


class ImagemFalsa:
    # Constante oferecida pela classe QImage real (não pelo módulo QtGui).
    Format_RGBA8888 = 17

    def __init__(self, caminho=None):
        try:
            self.dados = Path(caminho).read_bytes() if caminho else None
        except OSError:
            self.dados = None
        # Neste mock quatro bytes representam uma imagem RGBA de 1x1.
        if self.dados is not None and len(self.dados) != 4:
            self.dados = None

    def isNull(self):
        return self.dados is None

    def convertToFormat(self, formato):
        assert formato == QtFalso.Format_RGBA8888
        return self

    def width(self):
        return 1

    def height(self):
        return 1

    def bits(self):
        return self

    def asstring(self, tamanho):
        assert tamanho == 4
        return self.dados


class QtFalso:
    Format_RGBA8888 = 17
    QImage = ImagemFalsa


class UsoTextura:
    TEXTURE_BINDING = 1
    COPY_DST = 2


class Argumentos:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class WgpuFalso:
    TextureUsage = UsoTextura
    TexelCopyTextureInfo = Argumentos
    TexelCopyBufferLayout = Argumentos


class TexturaFalsa:
    def __init__(self, size, format, usage):
        self.size = size
        self.format = format
        self.usage = usage
        self.pixels = None


class FilaFalsa:
    def __init__(self):
        self.escritas = []

    def write_texture(self, destino, dados, layout, tamanho):
        assert destino.mip_level == 0
        assert destino.origin == (0, 0, 0)
        assert layout.bytes_per_row == tamanho[0] * 4
        destino.texture.pixels = bytes(dados)
        self.escritas.append(destino.texture)


class DispositivoFalso:
    def __init__(self):
        self.queue = FilaFalsa()
        self.texturas = []

    def create_texture(self, *, size, dimension, format, usage):
        assert dimension == "2d"
        textura = TexturaFalsa(size, format, usage)
        self.texturas.append(textura)
        return textura


class TestarTexturasDaGuiOriginal(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.caminho = Path(self.temp.name) / "pele.rgba"
        self.device = DispositivoFalso()
        self.cache = CacheTexturasVulkan(self.device, WgpuFalso, QtFalso)

    def test_branco_neutro_para_textura_ausente(self):
        textura = self.cache.obter(None)
        self.assertEqual(textura.pixels, bytes((255, 255, 255, 255)))
        self.assertIs(textura, self.cache.obter(""))
        self.assertEqual(len(self.device.texturas), 1)

    def test_carregamento_preserva_os_canais_rgba(self):
        self.caminho.write_bytes(bytes((17, 34, 51, 68)))
        textura = self.cache.obter(self.caminho)
        self.assertEqual(textura.pixels, bytes((17, 34, 51, 68)))
        self.assertEqual(textura.size, (1, 1, 1))
        self.assertEqual(textura.format, "rgba8unorm")
        self.assertEqual(textura.usage, 3)

    def test_arquivo_inalterado_reutiliza_textura_sem_upload(self):
        self.caminho.write_bytes(bytes((1, 2, 3, 4)))
        primeiro = self.cache.obter(self.caminho)
        segundo = self.cache.obter(self.caminho)
        self.assertIs(primeiro, segundo)
        self.assertEqual(len(self.device.queue.escritas), 1)

    def test_mesmo_caminho_editado_atualiza_gpu(self):
        self.caminho.write_bytes(bytes((1, 2, 3, 4)))
        primeiro = self.cache.obter(self.caminho)
        anterior = assinatura_arquivo(self.caminho)
        self.caminho.write_bytes(bytes((5, 6, 7, 8)))
        os.utime(self.caminho, ns=(anterior[3] + 2_000_000_000,
                                  anterior[3] + 2_000_000_000))
        segundo = self.cache.obter(self.caminho)
        self.assertIsNot(primeiro, segundo)
        self.assertEqual(segundo.pixels, bytes((5, 6, 7, 8)))
        self.assertEqual(len(self.device.queue.escritas), 2)

    def test_arquivo_aparece_depois_da_textura_fallback(self):
        inicial = self.cache.obter(self.caminho)
        self.assertEqual(inicial.pixels, bytes((255, 255, 255, 255)))
        self.caminho.write_bytes(bytes((9, 8, 7, 6)))
        posterior = self.cache.obter(self.caminho)
        self.assertIsNot(posterior, inicial)
        self.assertEqual(posterior.pixels, bytes((9, 8, 7, 6)))

    def test_arquivo_removido_descarta_textura_antiga(self):
        self.caminho.write_bytes(bytes((4, 3, 2, 1)))
        inicial = self.cache.obter(self.caminho)
        self.caminho.unlink()
        posterior = self.cache.obter(self.caminho)
        self.assertIsNot(posterior, inicial)
        self.assertEqual(posterior.pixels, bytes((255, 255, 255, 255)))

    def test_substituicao_atomica_com_mesmo_mtime_e_tamanho(self):
        self.caminho.write_bytes(bytes((4, 3, 2, 1)))
        inicial = self.cache.obter(self.caminho)
        atual = self.caminho.stat()
        substituto = Path(self.temp.name) / "novo.rgba"
        substituto.write_bytes(bytes((1, 2, 3, 4)))
        os.utime(substituto, ns=(atual.st_atime_ns, atual.st_mtime_ns))
        os.replace(substituto, self.caminho)
        posterior = self.cache.obter(self.caminho)
        self.assertIsNot(posterior, inicial)
        self.assertEqual(posterior.pixels, bytes((1, 2, 3, 4)))

    def test_caminhos_diferentes_tem_cache_independente(self):
        self.caminho.write_bytes(bytes((1, 2, 3, 4)))
        outro = Path(self.temp.name) / "olhos.rgba"
        outro.write_bytes(bytes((5, 6, 7, 8)))
        self.cache.obter(self.caminho)
        self.cache.obter(outro)
        self.assertEqual(len(self.device.texturas), 2)
        self.assertEqual(len(self.device.queue.escritas), 2)


if __name__ == "__main__":
    unittest.main()
