"""Cores de luz difusa e especular independentes, conforme .mhscene v5."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_lighting import cores_especulares_cena


class SceneSpecular(unittest.TestCase):
    def test_specular_color_is_independent_from_diffuse(self):
        scene = SimpleNamespace(lights=[SimpleNamespace(
            color=(0., 0., 0.), specular=SimpleNamespace(values=(1., .5, .2)))])
        data = cores_especulares_cena(scene)
        np.testing.assert_allclose(data[0], [1, .5, .2, 1])
        self.assertEqual(data.shape, (8, 4))
        self.assertEqual(data.dtype, np.float32)
        np.testing.assert_array_equal(data[1:], 0)

    def test_legacy_light_objects_keep_their_color(self):
        data = cores_especulares_cena(SimpleNamespace(lights=[SimpleNamespace(color=(.1, .2, .3))]))
        np.testing.assert_allclose(data[0], [.1, .2, .3, 1])

    def test_non_finite_specular_is_rejected(self):
        scene = SimpleNamespace(lights=[SimpleNamespace(color=(1, 1, 1), specular=(np.nan, 0, 0))])
        with self.assertRaises(ValueError):
            cores_especulares_cena(scene)
