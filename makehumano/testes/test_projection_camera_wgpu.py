"""Direção de projeção usa a transformação original da câmera/objeto."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "codigo/makehuman"
for directory in (ROOT, ROOT / "lib", ROOT / "core", ROOT / "shared"):
    sys.path.insert(0, str(directory))
import projection


class ProjectionCamera(unittest.TestCase):
    def direction(self, model):
        render_object = object()
        mesh = SimpleNamespace(object3d=render_object)

        def model_matrix(obj):
            self.assertIs(obj, render_object)
            return model

        camera = SimpleNamespace(eye=(0., 0., 10.), focus=(0., 0., 0.), getModelMatrix=model_matrix)
        with patch.object(projection.G, "app", SimpleNamespace(modelCamera=camera)):
            return projection.getCamera(mesh)

    def test_mesh_does_not_need_obsolete_transform_attribute(self):
        np.testing.assert_allclose(self.direction(np.eye(4)), [0., 0., 1.])

    def test_orbital_rotation_is_included_in_surface_facing_direction(self):
        rotation = np.eye(4)
        rotation[:3, :3] = [[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]]
        np.testing.assert_allclose(self.direction(rotation), [-1., 0., 0.], atol=1e-7)

    def test_translation_does_not_change_parallel_view_direction(self):
        model = np.eye(4)
        model[:3, 3] = [3., -2., 4.]
        np.testing.assert_allclose(self.direction(model), [0., 0., 1.])
