"""Regressões da composição alfa na viewport original do MakeHuman.

A seleção de pipeline usa exclusivamente flags de lib.object3d.Object3D.
O smoke Vulkan-GUI do CI valida criação efetiva do pipeline no dispositivo.
"""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))

from vulkan_material import parametros_material_vulkan, usa_transparencia_vulkan


def objeto(*, primitivas=0, opacidade=1.0, solido=True, shadeless=False,
           com_textura=True):
    return SimpleNamespace(
        solid=solido,
        shadeless=shadeless,
        nTransparentPrimitives=primitivas,
        isTextured=com_textura,
        texture="roupa.png",
        material=SimpleNamespace(
            diffuseColor=SimpleNamespace(values=(0.5, 0.7, 0.9)),
            opacity=opacidade,
        ),
    )


class TestarTransparenciaDaGuiOriginal(unittest.TestCase):
    def test_corpo_opaco_continua_no_pipeline_opaco(self):
        original = objeto()
        dados, _ = parametros_material_vulkan(original)
        self.assertFalse(usa_transparencia_vulkan(original, dados))
        np.testing.assert_array_equal(dados[4:], [0, 0, 0, 0])

    def test_roupa_com_primitivas_transparentes_usa_blend(self):
        original = objeto(primitivas=24)
        dados, caminho = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))
        self.assertEqual(dados[5], 1.0)
        self.assertEqual(dados[3], 1.0)
        self.assertEqual(caminho, "roupa.png")

    def test_material_com_opacidade_parcial_mesmo_sem_face_transparente(self):
        original = objeto(opacidade=0.35)
        dados, _ = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))
        self.assertEqual(dados[5], 0.0)
        self.assertAlmostEqual(float(dados[3]), 0.35)

    def test_opacidade_zero_nao_escreve_depth(self):
        original = objeto(opacidade=0.0)
        dados, _ = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))

    def test_wireframe_nao_usa_pipeline_de_transparencia(self):
        original = objeto(solido=False, primitivas=10, opacidade=0.2)
        dados, caminho = parametros_material_vulkan(original)
        self.assertFalse(usa_transparencia_vulkan(original, dados))
        self.assertEqual(dados[5], 0.0)
        self.assertEqual(dados[3], 1.0)
        self.assertIsNone(caminho)

    def test_shadeless_transparente_preserva_dois_controles(self):
        original = objeto(primitivas=1, shadeless=True)
        dados, _ = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))
        np.testing.assert_array_equal(dados[4:6], [1.0, 1.0])

    def test_alternancia_recalcula_flags_sem_cache_indevido(self):
        original = objeto(primitivas=3)
        dados, _ = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))
        original.nTransparentPrimitives = 0
        novos, _ = parametros_material_vulkan(original)
        self.assertFalse(usa_transparencia_vulkan(original, novos))
        self.assertEqual(novos[5], 0.0)

    def test_sem_textura_preserva_transparencia_de_material(self):
        original = objeto(primitivas=2, com_textura=False)
        dados, caminho = parametros_material_vulkan(original)
        self.assertTrue(usa_transparencia_vulkan(original, dados))
        self.assertIsNone(caminho)
        self.assertEqual(dados[5], 1.0)

    def test_uniform_continua_layout_96_bytes(self):
        original = objeto(primitivas=1, opacidade=0.5)
        dados, _ = parametros_material_vulkan(original)
        uniforme = np.concatenate(
            (np.eye(4, dtype=np.float32).T.reshape(-1), dados)
        )
        self.assertEqual(uniforme.nbytes, 96)
        self.assertEqual(uniforme[19], np.float32(0.5))
        self.assertEqual(uniforme[21], 1.0)


if __name__ == "__main__":
    unittest.main()
