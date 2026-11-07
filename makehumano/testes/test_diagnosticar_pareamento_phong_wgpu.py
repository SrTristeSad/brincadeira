"""Testes CPU das transformações diagnósticas, sem GPU."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosticar_pareamento_phong import (
    trocar_vermelho_azul, decodificar_srgb_rgb, _camera_igual
)


class TestarDiagnosticoDeCanais(unittest.TestCase):
    def test_inversao_rb_mantem_alfa(self):
        imagem = np.array([[[25, 50, 200, 128]]], dtype=np.uint8)
        saida = trocar_vermelho_azul(imagem)
        self.assertEqual(saida.tolist(), [[[200, 50, 25, 128]]])
        self.assertEqual(imagem.tolist(), [[[25, 50, 200, 128]]])

    def test_decodificacao_srgb_meio_para_linear(self):
        imagem = np.array([[[188, 188, 188, 255]]], dtype=np.uint8)
        saida = decodificar_srgb_rgb(imagem)
        self.assertTrue(all(abs(int(x)-128)<=1 for x in saida[0,0,:3]))
        self.assertEqual(saida[0,0,3],255)

    def test_camera_mismatch_nao_e_aceito(self):
        c = {
            "fov":90,"centro":[0,.11924934387207031,0],"radius":12.251182769327169,
            "projecao":0,"near":-100,"far":100,"zoom":1.,
            "rotacao_horizontal":0.,"inclinacao_vertical":0.,"translation":[0,0,0],
            "view":np.eye(4).tolist(),"proj":np.eye(4).tolist()
        }
        outro = dict(c, radius=12.35)
        result = _camera_igual(c,outro)
        self.assertFalse(result["radius"])
        self.assertTrue(result["fov"])


if __name__ == "__main__":
    unittest.main()
