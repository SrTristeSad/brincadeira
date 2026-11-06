"""Altura, geometria e seleção compartilham displacement sem mutação."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_displacement import amostrar_altura, posicoes_render
from vulkan_material_maps import parametros_mapa
from vulkan_picking import selecionar_cor, selecionar_profundidade
from vulkan_scene import preparar_malha_original, ordenar_objetos_vulkan


class Displacement(unittest.TestCase):
    def obj(self, **material):
        values = dict(displacementMapTexture=np.full((2, 2, 1), 255, np.uint8),
                      displacementMapIntensity=.5, opacity=1., transparent=False,
                      shaderConfig={}, shaderParameters={})
        values.update(material)
        return SimpleNamespace(verts=np.array([[-.8, -.8, 0], [.8, -.8, 0], [.8, .8, 0], [-.8, .8, 0]], np.float32),
            norms=np.tile([2., 0., 0.], (4, 1)), UVs=np.zeros((4, 2), np.float32), hasUVs=True,
            material=SimpleNamespace(**values), primitives=np.array([[0, 1, 2, 3]], np.uint32),
            color=np.full((4, 4), 255, np.uint8), groups=[(0, 1)], clrid=lambda i: (10, 20, 30),
            pickable=True, visibility=True, priority=0, cameraMode=0, cull=0, depthless=False)

    def cam(self):
        identity = np.eye(4, dtype=np.float32)
        return SimpleNamespace(updated=True, getMatrices=lambda eye: (identity, identity),
                               getModelMatrix=lambda obj: identity)

    def test_bilinear_filter_and_qt_vertical_origin(self):
        image = np.array([[[0], [64]], [[128], [255]]], np.uint8)
        uv = np.array([[0, 1], [1, 1], [0, 0], [1, 0], [.5, .5]])
        np.testing.assert_allclose(amostrar_altura(image, uv), np.array([0, 64, 128, 255, 111.75])/255., atol=1e-7)

    def test_luminance_ignores_alpha(self):
        uv = [[.5, .5]]
        for pixel, height in (([128], 128/255), ([128, 0], 128/255),
                              ([255, 0, 0], 1/3), ([255, 0, 0, 0], 1/3)):
            np.testing.assert_allclose(amostrar_altura(np.array([[pixel]], np.uint8), uv), [height])

    def test_uvs_clamp_to_edge(self):
        image = np.array([[[0], [64]], [[128], [255]]], np.uint8)
        np.testing.assert_allclose(amostrar_altura(image, [[-8, 9], [4, -5]]), [0, 1])

    def test_positions_follow_normalized_normals_without_mutating_mesh(self):
        obj = self.obj()
        old, normals, uv = obj.verts.copy(), obj.norms.copy(), obj.UVs.copy()
        moved = posicoes_render(obj)
        np.testing.assert_allclose(moved, old+[.5, 0, 0])
        np.testing.assert_array_equal(obj.verts, old)
        np.testing.assert_array_equal(obj.norms, normals)
        np.testing.assert_array_equal(obj.UVs, uv)
        vertices, _ = preparar_malha_original(obj)
        np.testing.assert_array_equal(vertices[:, :3], moved)

    def test_disabled_or_zero_strength_does_not_open_missing_file(self):
        for values in ({"displacementMapIntensity": 0}, {"shaderConfig": {"displacement": False}}):
            obj = self.obj(displacementMapTexture="missing.png", **values)
            np.testing.assert_array_equal(posicoes_render(obj), obj.verts)

    def test_black_map_and_dynamic_image_updates(self):
        image = np.zeros((2, 2, 4), np.uint8)
        obj = self.obj(displacementMapTexture=image)
        np.testing.assert_array_equal(posicoes_render(obj), obj.verts)
        image[:] = 255
        self.assertFalse(np.array_equal(posicoes_render(obj), obj.verts))

    def test_original_uniform_names_are_respected(self):
        image = np.ones((1, 1, 1), np.uint8)
        obj = self.obj(shaderParameters={"displacementmapTexture": image, "displacementmapIntensity": [.25]})
        resource, strength = parametros_mapa(obj.material, "displacement")
        self.assertIs(resource, image)
        self.assertEqual(strength, .25)

    def test_picking_follows_moved_surface(self):
        obj = self.obj()
        self.assertEqual(selecionar_cor([obj], [self.cam()], 95, 50, 100, 100), (10, 20, 30))
        self.assertLess(selecionar_profundidade([obj], [self.cam()], 95, 50, 100, 100), 1.)
        obj.material.displacementMapIntensity = 0
        self.assertEqual(selecionar_cor([obj], [self.cam()], 95, 50, 100, 100), (0, 0, 0))

    def test_alpha_object_order_uses_moved_positions(self):
        moved, other = self.obj(transparent=True), self.obj(transparent=True, displacementMapIntensity=0)
        moved.norms[:] = [0., 0., 1.]
        other.verts[:, 2] = .25
        self.assertEqual([id(o) for o in ordenar_objetos_vulkan([moved, other], [self.cam()])], [id(other), id(moved)])

    def test_active_map_requires_uvs_and_valid_data(self):
        obj = self.obj()
        obj.hasUVs = False
        with self.assertRaises(ValueError):
            posicoes_render(obj)
        for pixels, uv in ((np.ones((1, 1, 3)), [[0, 0]]), (np.ones((1, 1, 1), np.uint8), [[np.nan, 0]])):
            with self.assertRaises(ValueError):
                amostrar_altura(pixels, uv)
