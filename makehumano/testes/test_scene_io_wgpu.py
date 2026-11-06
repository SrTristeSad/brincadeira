"""Persistência original de luzes e falhas de acesso no Python moderno."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared"):
    sys.path.insert(0, str(directory))

from scene import Scene
from vulkan_lighting import parametros_foco_atenuacao
import numpy as np


class ScenePersistence(unittest.TestCase):
    def test_original_light_controls_roundtrip(self):
        original = Scene()
        light = original.lights[0]
        light.position = (3., 4., 5.)
        light.focus = (1., 2., 0.)
        light.fov = 35.
        light.attenuation = .125
        light.areaLightSize = 7.
        light.specular = (.2, .4, .6)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "iluminação.mhscene")
            self.assertTrue(original.save(path))
            restored = Scene()
            self.assertTrue(restored.load(path))
        for attribute in ("position", "focus", "fov", "attenuation", "areaLightSize"):
            self.assertEqual(getattr(restored.lights[0], attribute), getattr(light, attribute))
        np.testing.assert_allclose(restored.lights[0].specular.values, light.specular.values)
        for actual, expected in zip(parametros_foco_atenuacao(restored), parametros_foco_atenuacao(original)):
            np.testing.assert_array_equal(actual, expected)

    def test_missing_scene_returns_false_and_preserves_current_lights(self):
        scene = Scene()
        lights = scene.lights
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(scene.load(str(Path(directory) / "missing.mhscene")))
        self.assertIs(scene.lights, lights)

    def test_save_permission_error_returns_false(self):
        scene = Scene()
        with patch("builtins.open", side_effect=PermissionError("read only")):
            self.assertFalse(scene.save("denied.mhscene"))
