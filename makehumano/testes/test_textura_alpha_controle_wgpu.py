"""Testa textura de controle sem GPU, sem Pillow nem Image do MakeHuman."""
import hashlib
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textura_alpha_controle import (
    dados_textura_alfa_parcial, bytes_png_textura_alfa_parcial,
    salvar_textura_alfa_parcial,
)
import tempfile
import struct


class TestControleTexturaAlfa(unittest.TestCase):
    def test_rgba_parcial_e_xadrez_cor(self):
        a = dados_textura_alfa_parcial()
        self.assertEqual(a.shape, (32, 32, 4))
        self.assertEqual(a.dtype, np.uint8)
        self.assertTrue(np.all(a[:, :, 3] == 128))
        self.assertFalse(np.array_equal(a[0, 0, :3], a[0, 9, :3]))

    def test_deterministico(self):
        self.assertEqual(
            hashlib.sha256(dados_textura_alfa_parcial().tobytes()).hexdigest(),
            hashlib.sha256(dados_textura_alfa_parcial().tobytes()).hexdigest()
        )

    def test_png_rgba8_com_hash_consistente(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo, meta = salvar_textura_alfa_parcial(
                Path(pasta) / "controle.png"
            )
            raw = Path(arquivo).read_bytes()
            self.assertEqual(raw, bytes_png_textura_alfa_parcial())
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(
                struct.unpack(">IIBBBBB", raw[16:29]),
                (32, 32, 8, 6, 0, 0, 0),
            )
            self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256_png"])
            self.assertEqual(meta["alfa_textura"], 128)

    def test_controle_opacidade_textura_255(self):
        pixels = dados_textura_alfa_parcial(alfa=255)
        self.assertTrue(np.all(pixels[:, :, 3] == 255))
        with tempfile.TemporaryDirectory() as pasta:
            path, meta = salvar_textura_alfa_parcial(Path(pasta) / "opaco.png", alfa=255)
            self.assertEqual(meta["alfa_textura"], 255)
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), meta["sha256_png"])
            self.assertNotEqual(Path(path).read_bytes(), bytes_png_textura_alfa_parcial())

    def test_varredura_a064_e_a192_preserva_rgb_xadrez(self):
        base = dados_textura_alfa_parcial(alfa=128)
        hashes = set()
        for alfa in (64, 128, 192, 255):
            rgba = dados_textura_alfa_parcial(alfa=alfa)
            self.assertTrue(np.array_equal(rgba[:, :, :3], base[:, :, :3]))
            self.assertTrue(np.all(rgba[:, :, 3] == alfa))
            raw = bytes_png_textura_alfa_parcial(alfa=alfa)
            hashes.add(hashlib.sha256(raw).hexdigest())
            with tempfile.TemporaryDirectory() as pasta:
                path, meta = salvar_textura_alfa_parcial(
                    Path(pasta) / f"a{alfa}.png", alfa=alfa
                )
                self.assertEqual(Path(path).read_bytes(), raw)
                self.assertEqual(meta["alfa_textura"], alfa)
        self.assertEqual(len(hashes), 4)

    def test_parametros_devem_ser_pareados(self):
        with self.assertRaises(ValueError):
            dados_textura_alfa_parcial(alfa=127)
        with self.assertRaises(ValueError):
            dados_textura_alfa_parcial(lado=64)


if __name__ == "__main__":
    unittest.main()
