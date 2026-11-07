"""Testes CPU do comparador de geometria, sem GUI ou GPU."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registrar_geometria_paridade import descrever_geometria


class TesteAssinaturasGeometria(unittest.TestCase):
    def setUp(self):
        self.mat = object()
        self.obj = SimpleNamespace(
            name="corpo", material=self.mat, visibility=True, solid=True,
            cameraMode=0,
            verts=np.array([[0., 0., 0.],[1., 0., 0.],[0., 1., 0.],[1., 1., 0.]], np.float32),
            norms=np.array([[0., 0., 1.]]*4, np.float32),
            primitives=np.array([[0, 1, 3, 2]], np.uint32),
        )

    def test_canoniza_buffers(self):
        a = descrever_geometria([self.obj], self.mat)
        b = SimpleNamespace(**vars(self.obj))
        b.verts = self.obj.verts.astype(">f4").copy(order="F")
        b.norms = self.obj.norms.astype(">f4").copy(order="F")
        b.primitives = self.obj.primitives.astype(">u4")
        segundo = descrever_geometria([b], self.mat)
        self.assertEqual(a["assinaturas"], segundo["assinaturas"])
        self.assertEqual(a["quantidade_vertices"], 4)

    def test_detecta_normal_alterada(self):
        a = descrever_geometria([self.obj], self.mat)
        b = SimpleNamespace(**vars(self.obj))
        b.norms = np.array(self.obj.norms)
        b.norms[2] = [0., 1., 0.]
        segundo = descrever_geometria([b], self.mat)
        self.assertNotEqual(a["assinaturas"]["normais"]["sha256"], segundo["assinaturas"]["normais"]["sha256"])

    def test_rejeita_normal_invalida(self):
        self.obj.norms[0,0] = np.nan
        with self.assertRaises(ValueError):
            descrever_geometria([self.obj], self.mat)


if __name__ == "__main__":
    unittest.main()
