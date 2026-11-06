"""Regressão: leitura de imagens Qt em NumPy 2 sem fromstring binário."""

from pathlib import Path
import sys
import unittest

import numpy as np
from PyQt5 import QtGui


APP = Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
sys.path.insert(0, str(APP / "lib"))

import image_qt  # noqa: E402


class TesteImagensQt(unittest.TestCase):
    def test_imagem_com_alpha(self):
        imagem = QtGui.QImage(2, 2, QtGui.QImage.Format_ARGB32)
        imagem.fill(QtGui.QColor(10, 20, 30, 40))
        pixels = image_qt.load(imagem)

        self.assertEqual(pixels.shape, (2, 2, 4))
        self.assertEqual(pixels.dtype, np.uint8)
        np.testing.assert_array_equal(pixels[0, 0], [10, 20, 30, 40])

    def test_imagem_rgb(self):
        imagem = QtGui.QImage(3, 1, QtGui.QImage.Format_RGB32)
        imagem.fill(QtGui.QColor(50, 60, 70))
        pixels = image_qt.load(imagem)

        self.assertEqual(pixels.shape, (1, 3, 3))
        np.testing.assert_array_equal(pixels[0, 1], [50, 60, 70])




class TesteGravacaoQt(unittest.TestCase):
    def test_rgba_save_and_reload_preserves_channels(self):
        import tempfile
        from image import Image
        pixels = np.tile(np.array([11, 79, 203, 61], dtype=np.uint8), (2, 3, 1))
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "imagem-portátil.png")
            Image(data=pixels).save(path)
            np.testing.assert_array_equal(Image(path=path).data, pixels)

    def test_image_to_qimage_handles_channels_and_unaligned_width(self):
        from image import Image
        for pixel, expected in [([31], [31, 31, 31, 255]), ([31, 45], [31, 31, 31, 45]),
                                ([11, 79, 203], [11, 79, 203, 255]), ([11, 79, 203, 61], [11, 79, 203, 61])]:
            with self.subTest(pixel=pixel):
                pixels = np.tile(np.array(pixel, np.uint8), (2, 3, 1))
                qimage = Image(data=pixels).toQImage()
                self.assertEqual(qimage.pixelColor(2, 1).getRgb(), tuple(expected))


if __name__ == "__main__":
    unittest.main()
