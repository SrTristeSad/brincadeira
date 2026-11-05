"""Teste diferencial: deformação de CPU wgpu x código original MakeHuman.

Confere o catálogo via o crawler ORIGINAL de targets.py e compara os
deslocamentos de vértices com algos3d.Target.apply(), sem usar uma segunda
implementação das fórmulas geométricas como referência.
"""

from pathlib import Path
import sys
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "codigo" / "makehuman"
sys.path.insert(0, str(APP / "lib"))
sys.path.insert(0, str(APP / "core"))
sys.path.insert(0, str(RAIZ))

import algos3d  # noqa: E402
import targets  # noqa: E402
from motor_wgpu.malha import carregar_obj, caminho_base_obj  # noqa: E402
from motor_wgpu.morphs import Deformador, ler_target  # noqa: E402
from motor_wgpu.modificadores import carregar_catalogo  # noqa: E402
from motor_wgpu.macro import ControladorMacros, fatores_alvo  # noqa: E402


class MalhaOriginalSimulada:
    """Apenas a interface exigida por Target.apply sem pose e sem display."""

    def __init__(self, posicoes):
        self.coord = posicoes.copy()
        self.atualizados = 0

    def markCoords(self, indices, coor=True):
        self.atualizados += 1


def aplicar_alvos_com_algos3d(malha_original, pesos):
    """Usa o método real algos3d.Target.apply sem depender de OpenGL."""
    for arquivo, (alvo, peso) in pesos.items():
        if peso == 0:
            continue
        target = algos3d.Target.__new__(algos3d.Target)
        target.verts = alvo.indices
        target.data = alvo.deslocamentos
        target.faces = np.array([], dtype=np.uint32)
        target.apply(malha_original, peso, update=False, calcNormals=False)


class TesteComparacaoOriginal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.malha = carregar_obj(caminho_base_obj())

    def test_todos_sliders_resolvem_no_crawler_original(self):
        """Valida que catalogação não perdeu fatores/targets do MakeHuman."""
        crawler = targets.FilesTargetsCrawler(str(APP / "data"))
        crawler.findTargets()
        sliders = carregar_catalogo()
        self.assertEqual(len(sliders), 238)
        comparados = 0
        for slider in sliders:
            for arquivo in (slider.negativo, slider.positivo):
                if arquivo is None:
                    continue
                # UniversalModifier usa groupName-targetName[-left|right].
                # Nos arquivos, 'targets' é um componente especial ignorado
                # pelo crawler e cada token 'macro' vira dependência.
                relativo = arquivo.relative_to(APP / "data" / "targets")
                chave = tuple(
                    parte for parte in (
                        relativo.parent.as_posix().replace("/", "-")
                        + "-" + relativo.stem
                    ).replace("_", "-").split("-")
                    if parte not in targets._value_cat
                )
                encontrados = crawler.groups.get(chave, [])
                self.assertEqual(
                    [Path(c.path) for c in encontrados], [arquivo],
                    msg=f"{slider.identificador}: grupo {chave!r}",
                )
                self.assertEqual(
                    list(encontrados[0].getVariables()), [],
                    msg=f"Dependência condicional não tratada em {arquivo}",
                )
                comparados += 1
        self.assertGreaterEqual(comparados, 450)

    def test_posicoes_macros_e_sliders_iguais_ao_algos3d(self):
        """Compara o conjunto de morphs com o método original, em duas poses."""
        m = self.malha
        deformador = Deformador(m)
        macros = ControladorMacros(deformador)
        catalogo = carregar_catalogo()
        olho = next(s for s in catalogo if s.identificador == "nose/nose-scale-horiz-decr|incr")
        torso = next(s for s in catalogo if s.identificador == "torso/torso-vshape-decr|incr")
        extra = {}
        for slider, valor in ((olho, -37), (torso, 66)):
            for caminho, peso in slider.pesos(valor).items():
                extra[str(caminho)] = (ler_target(caminho, len(m.posicoes_base)), peso)
        deformador.definir_pesos(extra)

        for perfil in (
            {"muscle": 0.8, "weight": 0.35, "gender": 0.7},
            {"muscle": 0.1, "weight": 0.9, "age": 0.76},
        ):
            with self.subTest(perfil=perfil):
                for chave, valor in perfil.items():
                    macros.perfil.definir(chave, valor)
                macros.perfil.definir_etnia("african", 0.65)
                deformados = macros.atualizar().copy()

                # Referência algos3d: target aplica individualmente os
                # deslocamentos nas posições da malha OBJ, sem GPU.
                esperado = MalhaOriginalSimulada(m.posicoes_base)
                ativos = {arquivo: par for arquivo, par in deformador._alvos.items()}
                aplicar_alvos_com_algos3d(esperado, ativos)
                np.testing.assert_allclose(
                    deformados[:, 0:3], esperado.coord[m.origens],
                    atol=2e-4, rtol=2e-5,
                )
                np.testing.assert_array_equal(
                    deformados[:, 6:8], m.vertices[:, 6:8]
                )
                self.assertTrue(np.isfinite(deformados).all())


if __name__ == "__main__":
    unittest.main()
