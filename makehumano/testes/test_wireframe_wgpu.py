"""Wireframe original mantém arestas de quads e não altera o objeto."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo/makehuman/lib"))
from vulkan_scene import arestas_wireframe, passes_wireframe


class Wireframe(unittest.TestCase):
    def test_quad_edges_do_not_include_triangulation_diagonals(self):
        self.assertEqual(arestas_wireframe([[0, 1, 2, 3]]).tolist(), [[0, 1], [0, 3], [1, 2], [2, 3]])

    def test_shared_edges_are_not_duplicated_and_degenerate_edges_are_removed(self):
        self.assertEqual(arestas_wireframe([[0, 1, 2, 0], [2, 1, 3, 2]]).tolist(),
                         [[0, 1], [0, 2], [1, 2], [1, 3], [2, 3]])

    def test_surface_and_lines_share_original_mesh_without_mutation(self):
        obj = SimpleNamespace(solid=False, primitives=np.array([[0, 1, 2, 3]]),
                              material=SimpleNamespace(shader="litsphere"), shadeless=False)
        fill, lines = list(passes_wireframe([obj]))
        self.assertIs(fill.primitives, obj.primitives)
        self.assertIsNone(fill.material.shader)
        self.assertFalse(fill.isTextured)
        self.assertTrue(lines.shadeless)
        self.assertEqual(lines.material.diffuseColor.values, (0, 0, 0))
        self.assertFalse(obj.solid)
        self.assertEqual(obj.material.shader, "litsphere")

    def test_solid_mesh_does_not_gain_extra_passes(self):
        obj = SimpleNamespace(solid=True)
        self.assertEqual(list(passes_wireframe([obj])), [obj])
