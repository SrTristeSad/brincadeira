"""Cópias CPU de texturas: pintura, atualização externa e recarga original."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared"):
    sys.path.insert(0, str(directory))
from image import Image
from vulkan_texture import getTexture, reloadTexture, reloadTextures
from object3d import Object3D


class TextureWorkingCopy(unittest.TestCase):
    def tearDown(self):
        reloadTextures()

    def test_render_object_exposes_same_editable_texture(self):
        source = Image(data=np.full((4, 4, 4), 255, np.uint8))
        obj = Object3D(SimpleNamespace(object=SimpleNamespace(texture=source)))
        texture = obj.textureTex
        self.assertIs(texture, getTexture(source))
        texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
        self.assertEqual(int(obj.textureTex.data[0, 0].sum()), 0)
        self.assertEqual(int(source.data[0, 0].sum()), 1020)

    def test_file_working_copy_survives_get_and_reload_restores_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            white = np.full((4, 4, 4), 255, np.uint8)
            Image(data=white).save(str(path))
            original_bytes = path.read_bytes()
            texture = getTexture(path)
            texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            self.assertIs(getTexture(path), texture)
            self.assertEqual(int(getTexture(path).data[0, 0].sum()), 0)
            self.assertEqual(path.read_bytes(), original_bytes)
            reloadTexture(path)
            np.testing.assert_array_equal(getTexture(path).data, white)

    def test_size_change_reloads_even_if_file_timestamp_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            stat = path.stat()
            texture = getTexture(path)
            new = np.zeros((7, 9, 4), np.uint8)
            new[:, :, 0] = np.arange(9)
            new[:, :, 3] = 255
            Image(data=new).save(str(path))
            self.assertNotEqual(path.stat().st_size, stat.st_size)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            self.assertIs(getTexture(path), texture)
            np.testing.assert_array_equal(texture.data, new)
