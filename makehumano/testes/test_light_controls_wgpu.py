"""Uniforms de foco/atenuação preservam cenas sem cone e sem falloff."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_lighting import parametros_foco_atenuacao


class LightControls(unittest.TestCase):
    def light(self, **kwargs):
        values = dict(position=(0, 0, 4), focus=(0, 0, 0), fov=180, attenuation=0)
        values.update(kwargs)
        return SimpleNamespace(**values)

    def pack(self, light):
        return parametros_foco_atenuacao(SimpleNamespace(lights=[light]))

    def test_old_point_light_keeps_no_cone_no_attenuation(self):
        directions, parameters = self.pack(self.light())
        self.assertEqual(directions[0, 3], -1)
        self.assertEqual(parameters[0, 0], 0)
        self.assertEqual(directions.shape, (8, 4))
        self.assertEqual(directions.dtype, np.float32)

    def test_full_spot_angle_and_normalized_focus(self):
        directions, _ = self.pack(self.light(fov=60))
        np.testing.assert_allclose(directions[0], [0, 0, -1, np.cos(np.pi/6)])

    def test_attenuation_coefficient_is_independent(self):
        _, parameters = self.pack(self.light(attenuation=.25))
        self.assertEqual(parameters[0, 0], .25)

    def test_zero_focus_is_invalid_only_when_cone_is_active(self):
        self.pack(self.light(position=(0, 0, 0)))
        with self.assertRaisesRegex(ValueError, "coincidem"):
            self.pack(self.light(position=(0, 0, 0), fov=45))

    def test_invalid_coefficients_and_focus_are_rejected(self):
        for values in ({"attenuation": -1}, {"attenuation": np.nan}, {"fov": np.inf},
                       {"focus": (np.nan, 0, 0), "fov": 30}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.pack(self.light(**values))

    def test_only_first_eight_lights_are_packed(self):
        directions, _ = parametros_foco_atenuacao(SimpleNamespace(lights=[self.light(fov=90)]*10))
        np.testing.assert_allclose(directions[:, 3], np.cos(np.pi/4))
