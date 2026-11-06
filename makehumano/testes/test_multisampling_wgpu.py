"""Ativação de alpha-to-coverage pelos controles originais."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_scene import alpha_to_coverage_vulkan


class Multisampling(unittest.TestCase):
    def obj(self, **material):
        return SimpleNamespace(material=SimpleNamespace(opacity=1., **material), nTransparentPrimitives=0)

    def test_a2c_requires_multisampling(self):
        obj = self.obj(transparent=True, alphaToCoverage=True)
        self.assertFalse(alpha_to_coverage_vulkan(obj, 1))
        self.assertTrue(alpha_to_coverage_vulkan(obj, 4))

    def test_original_control_and_opaque_surfaces(self):
        self.assertFalse(alpha_to_coverage_vulkan(self.obj(transparent=True, alphaToCoverage=False), 4))
        self.assertFalse(alpha_to_coverage_vulkan(self.obj(transparent=False, alphaToCoverage=True), 4))

    def test_lines_do_not_use_alpha_to_coverage(self):
        self.assertFalse(alpha_to_coverage_vulkan(self.obj(transparent=True), 4, linhas=True))

    def test_cutout_primitives_use_original_default(self):
        obj = self.obj(transparent=False)
        obj.nTransparentPrimitives = 1
        self.assertTrue(alpha_to_coverage_vulkan(obj, 4))

    def test_unsupported_sample_count_is_explicit(self):
        with self.assertRaises(ValueError):
            alpha_to_coverage_vulkan(self.obj(), 3)
