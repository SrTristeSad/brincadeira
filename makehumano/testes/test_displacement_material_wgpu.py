"""Roundtrip .mhmat e uniform legado de displacement do Material original."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared"):
    sys.path.insert(0, str(directory))
from material import Material
from vulkan_material_maps import parametros_mapa


class OriginalDisplacementMaterial(unittest.TestCase):
    def test_roundtrip_original_material_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            image = path/"height.png"
            image.write_bytes(b"resource path: decoding tested by GPU smoke")
            source = path/"source.mhmat"
            source.write_text("name Original\ndisplacementmapTexture height.png\ndisplacementmapIntensity 0.35\nshaderConfig displacement true\n", encoding="utf-8")
            material = Material()
            material.fromFile(str(source))
            resource, intensity = parametros_mapa(material, "displacement")
            self.assertEqual(Path(resource), image)
            self.assertEqual(intensity, .35)
            output = path/"output.mhmat"
            material.toFile(str(output))
            self.assertNotIn("shaderParam displacementmapIntensity", output.read_text())
            restored = Material()
            restored.fromFile(str(output))
            self.assertEqual(parametros_mapa(restored, "displacement"), (resource, intensity))

    def test_legacy_custom_uniform_keeps_effective_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/"height.png").write_bytes(b"resource")
            source = path/"legacy.mhmat"
            source.write_text("name Legacy\ndisplacementmapTexture height.png\ndisplacementmapIntensity 0.9\nshaderParam displacementmapIntensity 0.4\n", encoding="utf-8")
            material = Material()
            material.fromFile(str(source))
            self.assertEqual(material.displacementMapIntensity, .4)
            self.assertEqual(parametros_mapa(material, "displacement")[1], .4)
            material.toFile(str(path/"saved.mhmat"))
            text = (path/"saved.mhmat").read_text()
            self.assertIn("displacementmapIntensity 0.4", text)
            self.assertNotIn("shaderParam displacementmapIntensity", text)

    def test_material_intensity_is_protected_like_other_map_uniforms(self):
        with self.assertRaisesRegex(RuntimeError, "protected"):
            Material().setShaderParameter("displacementmapIntensity", .5)

    def test_disabled_config_survives_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"disabled.mhmat"
            material = Material()
            material.configureShading(displacement=False)
            material.toFile(str(path))
            restored = Material()
            restored.fromFile(str(path))
            self.assertFalse(restored.shaderConfig["displacement"])
