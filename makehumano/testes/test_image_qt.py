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


if __name__ == "__main__":
    unittest.main()
