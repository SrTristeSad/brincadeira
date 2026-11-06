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

    def test_substituicao_atomica_mesmo_mtime_e_tamanho_recarrega(self):
        """PNG substituído por editor externo não pode manter pixels obsoletos."""
        import struct
        import zlib

        def png_constante(valor):
            def bloco(nome, conteudo):
                return (struct.pack(">I", len(conteudo)) + nome + conteudo
                        + struct.pack(">I", zlib.crc32(nome + conteudo)))
            cabecalho = struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0)
            rgba = bytes((valor, valor, valor, 255))
            linhas = (b"\x00" + rgba * 4) * 4
            return (b"\x89PNG\r\n\x1a\n"
                    + bloco(b"IHDR", cabecalho)
                    + bloco(b"IDAT", zlib.compress(linhas, level=0))
                    + bloco(b"IEND", b""))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "texture.png"
            novo_caminho = Path(directory) / "texture-nova.png"
            path.write_bytes(png_constante(254))
            texture = getTexture(path)
            self.assertEqual(int(texture.data[0, 0, 0]), 254)
            anterior = path.stat()
            novo_caminho.write_bytes(png_constante(255))
            self.assertEqual(novo_caminho.stat().st_size, anterior.st_size)
            os.utime(novo_caminho, ns=(anterior.st_atime_ns, anterior.st_mtime_ns))
            os.replace(novo_caminho, path)
            depois = path.stat()
            self.assertEqual(depois.st_mtime_ns, anterior.st_mtime_ns)
            self.assertEqual(depois.st_size, anterior.st_size)
            self.assertTrue(depois.st_ino != anterior.st_ino
                            or depois.st_ctime_ns != anterior.st_ctime_ns)
            self.assertIs(getTexture(path), texture)
            self.assertEqual(int(texture.data[0, 0, 0]), 255)

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

    def test_material_resolved_path_and_original_path_reload_same_texture(self):
        from material import Material
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            material = Material()
            material.diffuseTexture = str(path)
            texture = getTexture(material.diffuseTexture)
            self.assertIs(getTexture(path), texture)
            texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            reloadTexture(path)
            self.assertEqual(int(getTexture(material.diffuseTexture).data[0, 0].sum()), 1020)

    def test_file_alias_shares_working_copy_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"texture.png"
            alias = Path(directory)/"alias.png"
            Image(data=np.full((4, 4, 4), 255, np.uint8)).save(str(path))
            try:
                alias.symlink_to(path)
            except OSError as exc:
                self.skipTest(f"Symlink indisponível: {exc}")
            texture = getTexture(path)
            self.assertIs(getTexture(alias), texture)
            texture.loadSubImage(Image(data=np.zeros((1, 1, 4), np.uint8)), 0, 0)
            reloadTexture(alias)
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
