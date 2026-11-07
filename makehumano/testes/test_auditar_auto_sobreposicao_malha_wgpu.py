"""Regressões CPU: auto-sobreposição projetada sem renderizador.

Teste de quad com triangulação e id de face, triângulos sobrepostos,
câmera/projeção, máscaras reais de cor e entradas malformadas.
"""
import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditar_auto_sobreposicao_malha import (
    auditar_corpo, incidencias_em_pontos, projetar_triangulos,
)


class CameraSintetica:
    updated = True

    def getMatrices(self, _eye):
        return np.eye(4, dtype=np.float64), np.eye(4, dtype=np.float64)

    def getModelMatrix(self, _obj):
        return np.eye(4, dtype=np.float64)


class TesteAutoSobreposicao(unittest.TestCase):
    def setUp(self):
        tri = np.array([
            [-0.6, -0.6, 0.0], [0.6, -0.6, 0.0], [0.0, 0.6, 0.0],
        ], np.float32)
        self.vertices = np.concatenate((
            tri, tri + [0, 0, 0.2]
        ), axis=0)
        self.faces = np.array([[0, 1, 2], [3, 4, 5]], np.uint32)
        self.camera = CameraSintetica()
        self.corpo = SimpleNamespace(
            verts=self.vertices, primitives=self.faces
        )

    def test_duas_faces_projetadas_com_profundidades_distintas(self):
        g = projetar_triangulos(
            self.vertices, self.faces,
            np.eye(4), np.eye(4), np.eye(4), 64, 64
        )
        m = incidencias_em_pontos(g, np.array([[32, 32], [0, 0]]))
        self.assertEqual(g["triangulos_projetaveis"], 2)
        self.assertEqual(m[0]["faces"], 2)
        self.assertEqual(m[0]["triangulos"], 2)
        self.assertAlmostEqual(m[0]["gap_depth_min"], 0.1)
        self.assertEqual(m[1]["faces"], 0)
        self.assertIsNone(m[1]["gap_depth_min"])

    def test_quad_com_duas_metades_nao_cria_duas_faces_pai(self):
        xy = np.array([
            [-0.8, -0.8, 0.0], [0.8, -0.8, 0.0],
            [0.8, 0.8, 0.0], [-0.8, 0.8, 0.0],
        ], np.float32)
        g = projetar_triangulos(
            xy, np.array([[0, 1, 2, 3]], np.int64),
            np.eye(4), np.eye(4), np.eye(4), 64, 64
        )
        self.assertEqual(g["triangulos_projetaveis"], 2)
        self.assertEqual(
            incidencias_em_pontos(g, np.array([[32, 32]]))[0]["faces"], 1
        )

    def test_auditoria_separa_pixels_z_e_controles(self):
        a = np.zeros((64, 64, 3), np.uint8)
        a[20:44, 20:44] = [100, 100, 100]
        b = a.copy()
        b[32, 32] = [200, 200, 200]
        resultado = auditar_corpo(
            self.corpo, self.camera, a, b,
            largura=64, altura=64, max_controles=30
        )
        self.assertTrue(resultado["nao_homologado"])
        self.assertEqual(resultado["pixels_alterados"]["pixels"], 1)
        self.assertEqual(
            resultado["pixels_alterados"]["com_pelo_menos_2_faces"], 1
        )
        self.assertEqual(
            resultado["pixels_alterados"]["amostras_yx_faces"],
            [[32, 32, 2]],
        )
        self.assertGreater(
            resultado["controle_silhueta_inalterada"]["pixels"], 0
        )
        self.assertEqual(
            resultado["sha256_rgb_sem_z"],
            hashlib.sha256(a.tobytes()).hexdigest()
        )

    def test_rejeita_indice_e_ponto_invalidos(self):
        with self.assertRaisesRegex(ValueError, "Índices"):
            projetar_triangulos(
                self.vertices, [[0, 1, 22]],
                np.eye(4), np.eye(4), np.eye(4), 64, 64
            )
        g = projetar_triangulos(
            self.vertices, self.faces, np.eye(4), np.eye(4),
            np.eye(4), 64, 64
        )
        with self.assertRaisesRegex(ValueError, "Pontos"):
            incidencias_em_pontos(g, np.array([4, 4]))
        with self.assertRaisesRegex(ValueError, "Capturas"):
            auditar_corpo(
                self.corpo, self.camera,
                np.zeros((64, 64, 4), np.uint8),
                np.zeros((64, 64, 4), np.uint8),
                largura=64, altura=64
            )

    def test_sem_falso_positivo_quando_cores_iguais(self):
        imagem = np.zeros((64, 64, 3), np.uint8)
        imagem[20:44, 20:44] = 100
        rel = auditar_corpo(
            self.corpo, self.camera, imagem, imagem.copy(),
            largura=64, altura=64, max_controles=10
        )
        self.assertEqual(rel["pixels_alterados"]["pixels"], 0)
        self.assertEqual(rel["pixels_alterados"]["max_faces"], 0)


if __name__ == "__main__":
    unittest.main()
