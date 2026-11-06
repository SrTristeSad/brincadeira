"""Controles originais de mapas e regras de profundidade da transparência."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_material_maps import parametros_mapa
from vulkan_scene import configuracao_raster_vulkan, objeto_translucido_vulkan


class MaterialMaps(unittest.TestCase):
    def material(self, **overrides):
        values = dict(shaderConfig={}, shaderParameters={}, opacity=1.0, transparent=False)
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_map_and_intensity_from_original_material(self):
        image = object()
        mat = self.material(specularMapTexture=image, specularMapIntensity=.4)
        self.assertEqual(parametros_mapa(mat, "specular"), (image, .4))

    def test_dynamic_shader_parameters_and_scalar_list(self):
        image = object()
        mat = self.material(shaderParameters={"transparencymapTexture": image,
                                              "transparencymapIntensity": [.3]})
        self.assertEqual(parametros_mapa(mat, "transparency"), (image, .3))

    def test_disabled_or_zero_intensity_does_not_load_missing_resource(self):
        for values in ({"shaderConfig": {"spec": False}}, {"specularMapIntensity": 0}):
            with self.subTest(values=values):
                mat = self.material(specularMapTexture="missing.png", **values)
                self.assertEqual(parametros_mapa(mat, "specular"), (None, 0))

    def test_active_missing_map_is_reported(self):
        with self.assertRaisesRegex(ValueError, "textura não encontrada"):
            parametros_mapa(self.material(transparencyMapTexture="missing.png"), "transparency")

    def test_pathlike_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.png"
            path.write_bytes(b"resource")
            self.assertEqual(parametros_mapa(self.material(specularMapTexture=path), "specular"), (path, 1))

    def test_non_finite_or_vector_intensity_is_rejected(self):
        for value in (float("nan"), float("inf"), [1, 2]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parametros_mapa(self.material(specularMapTexture=object(), specularMapIntensity=value), "specular")

    def test_transparency_map_disables_depth_write_even_without_transparent_flag(self):
        obj = SimpleNamespace(material=self.material(transparencyMapTexture=object()),
                              nTransparentPrimitives=0, cull=1, depthless=False)
        self.assertTrue(objeto_translucido_vulkan(obj))
        self.assertEqual(configuracao_raster_vulkan(obj), ("back", False, "less-equal"))
        obj.material.shaderConfig["transparency"] = False
        self.assertFalse(objeto_translucido_vulkan(obj))
        self.assertEqual(configuracao_raster_vulkan(obj), ("back", True, "less-equal"))
