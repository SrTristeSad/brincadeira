"""Composição alpha dentro de uma malha: câmera, quads e faces opacas."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_scene import preparar_malha_original


class TriangleSort(unittest.TestCase):
    def mesh(self, quads=False):
        width = 4 if quads else 3
        coords = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]])[:width]
        verts = np.concatenate([coords + [0, 0, z] for z in (-1, -8, -4)]).astype(np.float32)
        return SimpleNamespace(
            verts=verts, norms=np.tile([0, 0, 1], (len(verts), 1)),
            hasUVs=False, color=np.full((len(verts), 4), 255, np.uint8),
            primitives=np.arange(len(verts)).reshape(-1, width),
            nTransparentPrimitives=3, material=SimpleNamespace(opacity=1, transparent=False))

    def camera(self, reverse=False):
        view = np.eye(4)
        if reverse:
            view[0, 0] = view[2, 2] = -1
        return SimpleNamespace(updated=True, getMatrices=lambda eye: (np.eye(4), view),
                               getModelMatrix=lambda obj: np.eye(4))

    def test_sort_tracks_camera_and_preserves_original_faces(self):
        obj = self.mesh()
        original = obj.primitives.copy()
        _, indices = preparar_malha_original(obj, self.camera())
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [3, 6, 0])
        _, indices = preparar_malha_original(obj, self.camera(reverse=True))
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [0, 6, 3])
        np.testing.assert_array_equal(obj.primitives, original)

    def test_opaque_faces_stay_before_transparent_faces(self):
        obj = self.mesh()
        obj.nTransparentPrimitives = 2
        _, indices = preparar_malha_original(obj, self.camera())
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [0, 3, 6])

    def test_quad_triangles_are_interleaved_by_depth(self):
        obj = self.mesh(quads=True)
        _, indices = preparar_malha_original(obj, self.camera())
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [4, 4, 8, 8, 0, 0])

    def test_material_opacity_sorts_all_faces(self):
        obj = self.mesh()
        obj.nTransparentPrimitives = 0
        obj.material.opacity = 0.5
        _, indices = preparar_malha_original(obj, self.camera())
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [3, 6, 0])

    def test_degenerate_quad_triangles_do_not_break_sort_mask(self):
        obj = self.mesh(quads=True)
        obj.primitives[:, 3] = obj.primitives[:, 0]
        _, indices = preparar_malha_original(obj, self.camera())
        self.assertEqual(indices.reshape(-1, 3)[:, 0].tolist(), [4, 8, 0])
