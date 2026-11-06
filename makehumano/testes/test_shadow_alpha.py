"""UVs, canais e presets devem preservar a cobertura do Material original."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
import numpy as np
ROOT = Path(__file__).resolve().parents[1] / 'codigo/makehuman'
for path in (ROOT/'lib', ROOT/'core', ROOT/'shared'):
    sys.path.insert(0, str(path))
from vulkan_shadow_alpha import PixelsSombra, SURFACE_DTYPE, superficies
from image import Image
from vulkan_texture import getTexture, reloadTexture


class ShadowAlpha(unittest.TestCase):
    def test_packed_channels_preserve_odd_width_and_deduplicate_each_role(self):
        data = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)
        resource = SimpleNamespace(data=data)
        pixels = PixelsSombra()
        alpha = pixels.registrar(resource, alpha_only=True)
        self.assertEqual(alpha, (1, 3, 2, 1))
        self.assertEqual(pixels.registrar(resource, alpha_only=True), alpha)
        self.assertEqual(len(pixels.pixels()), 3)
        np.testing.assert_array_equal(pixels.pixels()[1:].view(np.uint8)[:6], data[:, :, 3].reshape(-1))
        luminance = pixels.registrar(resource)
        self.assertEqual(luminance, (3, 3, 2, 2))
        self.assertEqual(pixels.registrar(resource), luminance)
        np.testing.assert_array_equal(pixels.pixels()[3:].view('<u2'), data[:, :, :3].sum(axis=2).reshape(-1))
        self.assertEqual(SURFACE_DTYPE.itemsize, 80)

    def test_odd_texel_counts_pad_words_without_modifying_texels(self):
        resource = SimpleNamespace(data=np.array([[[1, 2, 3, 5], [255, 255, 255, 128], [255, 0, 0, 0]]], np.uint8))
        pixels = PixelsSombra()
        alpha = pixels.registrar(resource, alpha_only=True)
        luminance = pixels.registrar(resource)
        words = pixels.pixels()
        np.testing.assert_array_equal(words[alpha[0]:alpha[0]+1].view(np.uint8), [5, 128, 0, 0])
        np.testing.assert_array_equal(words[luminance[0]:].view('<u2'), [6, 765, 255, 0])

    def test_luminance_alpha_and_opaque_rgb(self):
        pixels = PixelsSombra()
        la = SimpleNamespace(data=np.array([[[40, 128]]], np.uint8))
        descriptor = pixels.registrar(la, alpha_only=True)
        self.assertEqual(int(pixels.pixels()[descriptor[0]] & 255), 128)
        rgb = SimpleNamespace(data=np.full((3, 7, 3), 63, np.uint8))
        self.assertEqual(pixels.registrar(rgb, alpha_only=True), (0, 0, 0, 0))
        self.assertNotEqual(pixels.registrar(rgb), (0, 0, 0, 0))

    def test_working_copy_and_reload_change_mask_pixels_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'texture.png'
            data = np.full((3, 5, 4), 255, np.uint8)
            Image(data=data).save(str(path))
            before = PixelsSombra()
            self.assertEqual(before.registrar(path, alpha_only=True), (0, 0, 0, 0))
            texture = getTexture(path)
            data[:, :, 3] = 0
            texture.loadImage(Image(data=data))
            painted = PixelsSombra()
            descriptor = painted.registrar(path, alpha_only=True)
            self.assertTrue(np.all(painted.pixels()[descriptor[0]:].view(np.uint8)[:15] == 0))
            reloadTexture(path)
            restored = PixelsSombra()
            self.assertEqual(restored.registrar(path, alpha_only=True), (0, 0, 0, 0))

    def surface(self, preset=None):
        material = SimpleNamespace(shader=('/data/shaders/glsl/'+preset) if preset else None,
            opacity=.5, shaderConfig={'diffuse': True}, shaderParameters={})
        texture = SimpleNamespace(data=np.array([[[255, 255, 255, 128]]], np.uint8))
        obj = SimpleNamespace(material=material, texture=texture, isTextured=True)
        vertices = np.ones((3, 12), np.float32)
        vertices[:, 6:8] = [[0, 0], [1, 0], [0, 1]]
        vertices[:, 11] = [.25, .5, .75]
        return superficies(obj, vertices, np.array([[0, 1, 2]]), PixelsSombra())

    def test_uvs_opacity_and_vertex_alpha_are_kept_in_bvh_surface_order(self):
        surface = self.surface()[0]
        np.testing.assert_array_equal(surface['uv01'], [0, 0, 1, 0])
        np.testing.assert_array_equal(surface['uv2_opacity'], [0, 1, .5, 0])
        np.testing.assert_array_equal(surface['vertex_alpha'][:3], [.25, .5, .75])
        self.assertGreater(surface['diffuse'][1], 0)

    def test_preset_alpha_contracts_match_original_fragment_paths(self):
        normalmap = self.surface('normalmap')[0]
        self.assertEqual(normalmap['uv2_opacity'][2], 1.)
        self.assertEqual(normalmap['diffuse'][1], 0)
        np.testing.assert_array_equal(normalmap['vertex_alpha'][:3], 1.)
        for preset in ('litsphere', 'toon', 'skin'):
            with self.subTest(preset=preset):
                surface = self.surface(preset)[0]
                self.assertEqual(surface['uv2_opacity'][2], .5)
                np.testing.assert_array_equal(surface['vertex_alpha'][:3], 1.)
        np.testing.assert_array_equal(self.surface('phong')[0]['vertex_alpha'][:3], [.25, .5, .75])
