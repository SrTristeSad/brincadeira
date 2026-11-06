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

    def test_relative_and_absolute_paths_share_working_copy_and_reload(self):
        # relpath não pode cruzar volumes no Windows (workspace D:, TEMP C:).
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory)/"texture.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            relative = os.path.relpath(path)
            texture = getTexture(relative)
            self.assertIs(getTexture(path.resolve()), texture)
            texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            reloadTexture(path.resolve())
            self.assertEqual(int(getTexture(relative).data[0, 0].sum()), 1020)

    def test_image_source_path_does_not_alias_file_working_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            source = Image(path=str(path))
            memory_texture = getTexture(source)
            disk_texture = getTexture(path)
            self.assertIsNot(memory_texture, disk_texture)
            memory_texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            self.assertEqual(int(getTexture(source).data[0, 0].sum()), 0)
            self.assertEqual(int(getTexture(path).data[0, 0].sum()), 1020)

    @unittest.skipUnless(os.name == "nt", "Separadores equivalentes no Windows")
    def test_windows_slashes_share_cache_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            forward = str(path).replace("\\", "/")
            backward = str(path).replace("/", "\\")
            texture = getTexture(forward)
            self.assertIs(getTexture(backward), texture)
            texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            reloadTexture(backward)
            self.assertEqual(int(getTexture(forward).data[0, 0].sum()), 1020)
