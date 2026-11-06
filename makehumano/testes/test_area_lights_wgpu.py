"""Amostragem de área preserva energia, centro e cena original."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_area_lights import amostrar_luzes, MAX_AMOSTRAS_AREA, MAX_LUZES_VULKAN
from vulkan_lighting import dados_iluminacao_cena, parametros_foco_atenuacao


class AreaLights(unittest.TestCase):
    def light(self, **overrides):
        values = dict(position=(1., 2., 5.), focus=(0., 0., 0.), color=(.2, .4, .6),
                      specular=(.6, .4, .2), fov=180., attenuation=.1, areaLights=1, areaLightSize=4.)
        values.update(overrides)
        return SimpleNamespace(**values)

    def scene(self, *lights):
        return SimpleNamespace(environment=SimpleNamespace(ambience=(.1, .1, .1)), lights=list(lights))

    def test_default_point_light_is_preserved(self):
        source = self.scene(self.light())
        sampled, count = amostrar_luzes(source)
        self.assertEqual(count, 1)
        for a, b in zip(dados_iluminacao_cena(sampled), dados_iluminacao_cena(source)):
            np.testing.assert_array_equal(a, b)
        self.assertEqual(sampled.lights[0]._peso_vulkan, 1.)

    def test_zero_size_is_exactly_one_point(self):
        sampled, count = amostrar_luzes(self.scene(self.light(areaLights=16, areaLightSize=0.)))
        self.assertEqual(count, 1)
        self.assertEqual(len(sampled.lights), 1)
        np.testing.assert_array_equal(sampled.lights[0].position, [1., 2., 5.])

    def test_samples_keep_energy_center_and_emitter_plane(self):
        for count in (2, 3, 4, 7, 16):
            with self.subTest(count=count):
                light = self.light(areaLights=count)
                sampled, first = amostrar_luzes(self.scene(light))
                positions = np.array([p.position for p in sampled.lights])
                self.assertEqual(first, count)
                self.assertAlmostEqual(sum(p._peso_vulkan for p in sampled.lights), 1.)
                np.testing.assert_allclose(positions.mean(axis=0), light.position, atol=1e-8)
                normal = np.array(light.focus) - light.position
                np.testing.assert_allclose((positions-light.position) @ normal, 0, atol=1e-8)
                self.assertGreater(float(np.ptp(positions, axis=0).max()), 0)

    def test_area_does_not_mutate_original_values(self):
        light = self.light(areaLights=100)
        original = vars(light).copy()
        sampled, count = amostrar_luzes(self.scene(light))
        self.assertEqual(vars(light), original)
        self.assertEqual(count, MAX_AMOSTRAS_AREA)
        self.assertEqual(len(sampled.lights), MAX_AMOSTRAS_AREA)

    def test_sampling_is_repeatable_and_size_scales_offsets(self):
        light = self.light(areaLights=8, areaLightSize=1.)
        a, _ = amostrar_luzes(self.scene(light))
        b, _ = amostrar_luzes(self.scene(light))
        np.testing.assert_array_equal([p.position for p in a.lights], [p.position for p in b.lights])
        light.areaLightSize = 2.
        c, _ = amostrar_luzes(self.scene(light))
        np.testing.assert_allclose(np.array([p.position for p in c.lights])-light.position,
                                   2.*(np.array([p.position for p in a.lights])-light.position))

    def test_multiple_emitters_keep_independent_energy(self):
        source = self.scene(*[self.light(areaLights=16) for _ in range(10)])
        sampled, first = amostrar_luzes(source)
        self.assertEqual(first, 16)
        self.assertEqual(len(sampled.lights), MAX_LUZES_VULKAN)
        _, parameters = parametros_foco_atenuacao(sampled, MAX_LUZES_VULKAN)
        self.assertAlmostEqual(float(parameters[:, 1].sum()), 8.)

    def test_invalid_samples_and_size_are_reported(self):
        for values in ({"areaLights": 0}, {"areaLights": 1.5}, {"areaLights": np.nan},
                       {"areaLights": 2, "areaLightSize": -1}, {"areaLights": 2, "areaLightSize": np.inf}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                amostrar_luzes(self.scene(self.light(**values)))

    def test_coincident_focus_can_sample_omnidirectional_area(self):
        sampled, _ = amostrar_luzes(self.scene(self.light(position=(0, 0, 0), areaLights=4)))
        self.assertTrue(np.isfinite([p.position for p in sampled.lights]).all())
