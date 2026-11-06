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
    def test_unknown_light_attribute_uses_normal_python_lookup(self):
        light = Scene().lights[0]
        self.assertFalse(hasattr(light, "optional_plugin_parameter"))
        self.assertEqual(getattr(light, "optional_plugin_parameter", 7), 7)
        with self.assertRaises(AttributeError):
            _ = light.optional_plugin_parameter

    def test_original_light_controls_roundtrip(self):
        original = Scene()
        light = original.lights[0]
        light.position = (3., 4., 5.)
        light.focus = (1., 2., 0.)
        light.fov = 35.
        light.attenuation = .125
        light.areaLightSize = 7.
        light.areaLights = 12
        light.specular = (.2, .4, .6)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "iluminação.mhscene")
            self.assertTrue(original.save(path))
            restored = Scene()
            self.assertTrue(restored.load(path))
        for attribute in ("position", "focus", "fov", "attenuation", "areaLightSize", "areaLights"):
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

    def test_truncated_scene_keeps_existing_environment_and_lights(self):
        source = Scene()
        source.environment.ambience = (.9, .8, .7)
        scene = Scene()
        lights, environment = scene.lights, scene.environment
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.mhscene"
            self.assertTrue(source.save(str(path)))
            path.write_bytes(path.read_bytes()[:-1])
            self.assertFalse(scene.load(str(path)))
        self.assertIs(scene.lights, lights)
        self.assertIs(scene.environment, environment)
