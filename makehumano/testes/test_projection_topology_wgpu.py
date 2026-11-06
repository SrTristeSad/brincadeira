"""Topologia usada pelos exportadores UV originais, sem Qt nem GPU."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'codigo/makehuman/lib'))
from projection_topology import arestas_uv


class UVEdges(unittest.TestCase):
    def test_shared_edge_and_degenerate_quad_are_not_duplicated(self):
        faces = np.array([[0, 1, 2, 3], [3, 2, 4, 4]], np.uint32)
        expected = [[0, 1], [0, 3], [1, 2], [2, 3], [2, 4], [3, 4]]
        np.testing.assert_array_equal(arestas_uv(faces), expected)
        np.testing.assert_array_equal(faces, [[0, 1, 2, 3], [3, 2, 4, 4]])

    def test_large_indices_do_not_wrap_or_collide(self):
        faces = np.array([[0, 65536, 131072], [1, 65537, 4294967295]], np.uint32)
        expected = [[0, 65536], [0, 131072], [1, 65537], [1, 4294967295],
                    [65536, 131072], [65537, 4294967295]]
        np.testing.assert_array_equal(arestas_uv(faces), expected)
        self.assertEqual(arestas_uv(faces).dtype, np.uint32)

    def test_empty_faces_and_invalid_indices(self):
        self.assertEqual(arestas_uv(np.empty((0, 4), np.uint32)).shape, (0, 2))
        for invalid in ([[0, -1, 2]], [[0, 2**32, 2]], [[0., 1., 2.]], [0, 1]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                arestas_uv(invalid)


if __name__ == '__main__':
    unittest.main()
