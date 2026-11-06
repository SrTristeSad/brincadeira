"""Layout e invariantes da hierarquia usada pela oclusão WGSL."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'codigo/makehuman/lib'))
from vulkan_shadows import construir_bvh, NODE_DTYPE, preparar_buffers, reajustar_bvh


class ShadowBVH(unittest.TestCase):
    def test_empty_and_single_leaf_storage_layout(self):
        nodes, triangles = construir_bvh([])
        self.assertEqual(nodes.shape, (0,))
        self.assertEqual(triangles.shape, (0, 3, 4))
        self.assertEqual(NODE_DTYPE.itemsize, 48)
        source = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], np.float32)
        nodes, packed = construir_bvh(source)
        np.testing.assert_array_equal(nodes['span'][0], [0, 1, 1, 0])
        np.testing.assert_array_equal(packed[:, :, :3], source)
        np.testing.assert_array_equal(packed[:, :, 3], 0)

    def test_threaded_tree_covers_every_triangle_with_valid_bounds(self):
        source = np.random.default_rng(9).normal(size=(103, 3, 3)).astype(np.float32)
        original = source.copy()
        nodes, packed = construir_bvh(source, leaf_size=4)
        recovered = []
        for index, node in enumerate(nodes):
            first, count, escape, _ = map(int, node['span'])
            self.assertGreater(escape, index)
            self.assertLessEqual(escape, len(nodes))
            if count:
                leaf = packed[first:first+count, :, :3]
                self.assertLessEqual(count, 4)
                self.assertTrue(np.all(leaf >= node['minimum'][:3]))
                self.assertTrue(np.all(leaf <= node['maximum'][:3]))
                recovered.extend(leaf.tolist())
            else:
                left = index+1
                right = int(nodes['span'][left, 2])
                self.assertLess(right, escape)
                self.assertEqual(int(nodes['span'][right, 2]), escape)
                for child in (left, right):
                    self.assertTrue(np.all(nodes['minimum'][child, :3] >= node['minimum'][:3]))
                    self.assertTrue(np.all(nodes['maximum'][child, :3] <= node['maximum'][:3]))
        self.assertEqual(sorted(map(str, recovered)), sorted(map(str, source.tolist())))
        np.testing.assert_array_equal(source, original)

    def test_coincident_centers_still_terminate(self):
        source = np.zeros((65, 3, 3), np.float32)
        nodes, triangles = construir_bvh(source, leaf_size=2)
        self.assertEqual(len(triangles), 65)
        self.assertEqual(int(nodes['span'][0, 2]), len(nodes))
        self.assertLess(len(nodes), 2*len(source))

    def test_refit_bounds_follow_deformation_without_reordering_topology(self):
        source = np.random.default_rng(1).normal(size=(71, 3, 3)).astype(np.float32)
        nodes, packed, order, levels = construir_bvh(source, metadata=True)
        spans = nodes['span'].copy()
        source[:, :, 0] *= -3
        source[:, :, 1] += 20
        packed = reajustar_bvh(source, nodes, order, levels)
        np.testing.assert_array_equal(nodes['span'], spans)
        np.testing.assert_array_equal(packed[:, :, :3], source[order])
        for index, node in enumerate(nodes):
            escape = int(node['span'][2])
            leaves = nodes[index:escape]
            leaves = leaves[leaves['span'][:, 1] > 0]
            points = np.concatenate([packed[int(n['span'][0]):int(n['span'][0]+n['span'][1]), :, :3]
                                     for n in leaves])
            np.testing.assert_allclose(node['minimum'][:3], points.min(axis=(0, 1)))
            np.testing.assert_allclose(node['maximum'][:3], points.max(axis=(0, 1)))

    def test_invalid_geometry_is_not_silently_ignored(self):
        for source in (np.zeros((1, 3)), np.full((1, 3, 3), np.nan)):
            with self.assertRaises(ValueError):
                construir_bvh(source)
        with self.assertRaises(ValueError):
            construir_bvh(np.zeros((1, 3, 3)), leaf_size=0)

    def test_gpu_cache_reuses_identical_geometry_and_invalidates_deformation(self):
        from unittest.mock import patch
        triangles = np.zeros((1, 3, 3), np.float32)
        uploads = []
        def upload(**kwargs):
            uploads.append(kwargs['data'].copy())
            return object()
        scene = SimpleNamespace(device=SimpleNamespace(create_buffer_with_data=upload),
                                wgpu=SimpleNamespace(BufferUsage=SimpleNamespace(STORAGE=1)))
        from vulkan_shadow_alpha import SURFACE_DTYPE
        surfaces = np.zeros(1, SURFACE_DTYPE)
        pixels = np.array([0xffffffff], np.uint32)
        with patch('vulkan_shadows.dados_cena', return_value=(triangles, surfaces, pixels)):
            a = preparar_buffers(scene, [], [])
            b = preparar_buffers(scene, [], [])
            self.assertIs(a[0], b[0])
            self.assertEqual(len(uploads), 4)
            triangles[0, 0, 0] = 1
            c = preparar_buffers(scene, [], [])
            self.assertIsNot(a[0], c[0])
            self.assertEqual(len(uploads), 6)
            pixels[0] = 0
            d = preparar_buffers(scene, [], [])
            self.assertIs(c[0], d[0])
            self.assertIsNot(c[3], d[3])
            self.assertEqual(len(uploads), 8)
            surfaces['uv2_opacity'][0, 2] = .5
            e = preparar_buffers(scene, [], [])
            self.assertIs(d[0], e[0])
            self.assertIsNot(d[2], e[2])
            self.assertEqual(len(uploads), 10)
