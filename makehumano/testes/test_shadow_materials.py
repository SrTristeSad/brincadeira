"""Seleção de oclusores usa controles e geometria do MakeHuman original."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import numpy as np
ROOT = Path(__file__).resolve().parents[1] / 'codigo/makehuman'
for path in (ROOT/'lib', ROOT/'core', ROOT/'shared'):
    sys.path.insert(0, str(path))
from vulkan_shadows import triangulos_cena


class ShadowMaterials(unittest.TestCase):
    def setUp(self):
        self.obj = SimpleNamespace(visibility=True, cameraMode=0, depthless=False,
            material=SimpleNamespace(castShadows=True, receiveShadows=True, shader=None,
                                     opacity=1., transparent=False, shaderConfig={}),
            verts=np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32),
            norms=np.tile([0., 0., 1.], (4, 1)), hasUVs=False,
            color=np.full((4, 4), 255, np.uint8), isTextured=False, texture=None,
            nTransparentPrimitives=0, primitives=np.array([[0, 1, 2, 3]], np.uint32))
        self.model = np.eye(4, dtype=np.float32)
        self.cameras = [SimpleNamespace(getModelMatrix=lambda obj: self.model)]

    def triangles(self, production=False):
        return triangulos_cena([self.obj], self.cameras, production)

    def test_original_cast_and_receive_flags_are_independent(self):
        self.assertEqual(self.triangles().shape, (2, 3, 3))
        self.obj.material.receiveShadows = False
        self.assertEqual(len(self.triangles()), 2)
        self.obj.material.castShadows = False
        self.assertEqual(len(self.triangles()), 0)

    def test_invisible_auxiliary_and_production_excluded_do_not_cast(self):
        for attribute, value in [('visibility', False), ('depthless', True), ('cameraMode', 1)]:
            previous = getattr(self.obj, attribute)
            setattr(self.obj, attribute, value)
            self.assertEqual(len(self.triangles()), 0)
            setattr(self.obj, attribute, previous)
        self.obj.excludeFromProduction = True
        self.assertEqual(len(self.triangles()), 2)
        self.assertEqual(len(self.triangles(production=True)), 0)

    def test_translucency_and_alpha_cutouts_are_not_opaque_occluders(self):
        self.obj.material.transparent = True
        self.assertEqual(len(self.triangles()), 0)
        self.obj.material.transparent = False
        self.obj.material.opacity = .5
        self.assertEqual(len(self.triangles()), 0)
        self.obj.material.opacity = 1.
        self.obj.color[0, 3] = 0
        self.assertEqual(len(self.triangles()), 0)
        self.obj.color[0, 3] = 255
        self.obj.isTextured = True
        self.obj.texture = SimpleNamespace(data=np.array([[[255, 255, 255, 0]]], np.uint8))
        self.assertEqual(len(self.triangles()), 0)
        self.obj.texture.data[:, :, 3] = 255
        self.assertEqual(len(self.triangles()), 2)

    def test_xray_is_not_an_opaque_occluder(self):
        self.obj.material.shader = '/data/shaders/glsl/xray'
        self.assertEqual(len(self.triangles()), 0)

    def test_model_transform_and_transparent_face_mask_preserve_original_arrays(self):
        original = self.obj.verts.copy()
        self.model[:3, 3] = [10, 20, 30]
        result = self.triangles()
        np.testing.assert_array_equal(result, original[[[0, 1, 2], [0, 2, 3]]] + [10, 20, 30])
        np.testing.assert_array_equal(self.obj.verts, original)
        self.obj.primitives = np.array([[0, 1, 2, 3], [0, 1, 2, 3]], np.uint32)
        self.obj.nTransparentPrimitives = 1
        np.testing.assert_array_equal(self.triangles(), result)
