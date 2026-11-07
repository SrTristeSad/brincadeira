"""Regressões CPU da validação RGB de MSAA/A2C; não requer GPU."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosticar_a2c_msaa import (
    CONTROLES, comparar_rgb, metadados_rgb, validar_controles,
)


class TesteDiagnosticoA2C(unittest.TestCase):
    def setUp(self):
        self.imagem = np.zeros((3, 4, 3), dtype=np.uint8)

    def test_hash_e_dimensoes(self):
        d = metadados_rgb(self.imagem)
        self.assertEqual(d["dimensoes"], [4, 3])
        self.assertEqual(len(d["sha256_rgb"]), 64)

    def test_diferenca_quantificada_sem_confundir_amostras(self):
        alterada = self.imagem.copy()
        alterada[0, 0, 1] = 9
        r = comparar_rgb(self.imagem, alterada, tolerancia=8)
        self.assertEqual(r["pixels_divergentes"], 1)
        self.assertAlmostEqual(r["fracao_divergente"], 1 / 12)
        self.assertFalse(r["arrays_identicos"])

    def test_rejeita_formato_ou_dimensoes_erradas(self):
        with self.assertRaises(ValueError):
            metadados_rgb(np.zeros((2, 2, 4), dtype=np.uint8))
        with self.assertRaises(ValueError):
            comparar_rgb(self.imagem, np.zeros((4, 4, 3), dtype=np.uint8))

    def test_recusa_prova_de_pipeline_ausente(self):
        registros = {
            nome: {
                "amostras": config[0],
                "a2c_elegivel": config[1],
                "pipeline_a2c_observado": config[1],
                "captura_rgb": True,
                "sha256_rgb": "a" * 64,
            }
            for nome, config in CONTROLES.items()
        }
        self.assertTrue(validar_controles(registros))
        registros["4x_com_a2c"]["pipeline_a2c_observado"] = False
        with self.assertRaises(ValueError):
            validar_controles(registros)

    def test_rejeita_controle_ausente(self):
        with self.assertRaises(ValueError):
            validar_controles({})


if __name__ == "__main__":
    unittest.main()
