"""Testes CPU da transformação diagnóstica eye→world."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compensar_luz_eye_legacy import posicao_mundo_para_luz_eye_legacy


class TesteLuzEyeLegada(unittest.TestCase):
    def test_identidade(self):
        self.assertEqual(
            posicao_mundo_para_luz_eye_legacy(np.eye(4), [-10.99, 20, 20]),
            [-10.99, 20., 20.]
        )

    def test_view_transladada(self):
        view=np.eye(4)
        view[:3,3]=[0,-.11924934387207031,-12.251182769327169]
        mundo=posicao_mundo_para_luz_eye_legacy(view,[-10.99,20.,20.])
        self.assertTrue(np.allclose(mundo,[-10.99,20.11924934387207,32.25118276932717]))
        self.assertTrue(np.allclose(view @ [*mundo,1],[-10.99,20,20,1]))

    def test_view_singular_rejeitada(self):
        with self.assertRaises(ValueError):
            posicao_mundo_para_luz_eye_legacy(np.zeros((4,4)),[-10,0,0])


if __name__ == "__main__":
    unittest.main()
