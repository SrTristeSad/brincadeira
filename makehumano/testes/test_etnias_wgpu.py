"""Comparação da normalização herdada e atualização dos targets em Vulkan.

A referência é Human._setEthnicVals extraído diretamente do human.py original,
sem importar a GUI. Não inferimos identidade étnica: são pesos de morph targets.
"""

import ast
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
import unittest

import numpy as np


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.macro import (
    ETNIAS, ETNIAS_PADRAO, PerfilMacro, ControladorMacros, arquivos_macro,
    fatores_alvo,
)
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.morphs import Deformador


def metodo_original():
    caminho = RAIZ / "codigo" / "makehuman" / "apps" / "human.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    human = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == "Human")
    metodo = next(n for n in human.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_setEthnicVals")
    modulo = ast.Module(body=[metodo], type_ignores=[])
    ast.fix_missing_locations(modulo)
    escopo = {}
    exec(compile(modulo, str(caminho), "exec"), escopo)
    return escopo["_setEthnicVals"]


def instancia_original(metodo, proporcoes=None):
    proporcoes = ETNIAS_PADRAO if proporcoes is None else proporcoes
    obj = SimpleNamespace(**{chave + "Val": proporcoes[chave] for chave in ETNIAS})
    obj._setEthnicVals = MethodType(metodo, obj)
    return obj


class TesteEtnias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = metodo_original()

    def comparar(self, perfil, original):
        fatores = perfil.fatores()
        for nome in ETNIAS:
            with self.subTest(nome=nome):
                self.assertAlmostEqual(
                    fatores[nome], getattr(original, nome + "Val"), places=9
                )
        self.assertAlmostEqual(sum(fatores[n] for n in ETNIAS), 1.0, places=9)

    def test_sequencia_reproduz_original_sem_perder_proporcoes(self):
        referencia = instancia_original(self.original)
        perfil = PerfilMacro()
        self.comparar(perfil, referencia)
        acoes = [
            ("african", 0.75),
            ("caucasian", 0.5),
            ("asian", 0.0),
            ("african", 1.0),
            ("asian", 0.34),
            ("caucasian", 0.8),
            ("asian", 0.2),
            ("caucasian", 0.0),
            ("african", 0.9998),
        ]
        for chave, valor in acoes:
            with self.subTest(chave=chave, valor=valor):
                setattr(referencia, chave + "Val", valor)
                referencia._setEthnicVals(chave)
                perfil.definir_etnia(chave, valor)
                self.comparar(perfil, referencia)

    def test_valores_limite_com_outros_em_zero(self):
        casos = [
            ({"african": 0.0, "asian": 0.0, "caucasian": 0.0}, "african", 0.0),
            ({"african": 0.0, "asian": 0.0, "caucasian": 0.0}, "african", 0.4),
            ({"african": 0.0, "asian": 0.0, "caucasian": 0.0}, "asian", 0.9997),
            ({"african": 0.0, "asian": 0.0, "caucasian": 0.0}, "asian", 1.0),
        ]
        for estado, chave, valor in casos:
            with self.subTest(chave=chave, valor=valor):
                ref = instancia_original(self.original, estado)
                perfil = PerfilMacro()
                perfil.etnias = estado.copy()
                setattr(ref, chave + "Val", valor)
                ref._setEthnicVals(chave)
                perfil.definir_etnia(chave, valor)
                self.comparar(perfil, ref)

    def test_validacao_e_restauração(self):
        perfil = PerfilMacro()
        for chave, valor, erro in [
            ("nao_existe", 0.5, KeyError),
            ("asian", -0.2, ValueError),
            ("asian", 1.5, ValueError),
            ("asian", float("nan"), ValueError),
            ("asian", float("inf"), ValueError),
        ]:
            with self.assertRaises(erro):
                perfil.definir_etnia(chave, valor)
        perfil.definir_etnia("asian", 0.8)
        perfil.restaurar()
        self.assertEqual(perfil.etnias, ETNIAS_PADRAO)

    def test_pesos_de_arquivo_racial_original(self):
        arquivo = next(a for a in arquivos_macro() if a.name == "african-female-young.target")
        perfil = PerfilMacro()
        self.assertAlmostEqual(fatores_alvo(arquivo, perfil.fatores()), 1.0 / 6)
        perfil.definir_etnia("african", 0.75)
        self.assertAlmostEqual(fatores_alvo(arquivo, perfil.fatores()), 0.75 * 0.5)

    def test_malha_real_muda_e_volta_ao_inicio(self):
        malha = carregar_obj(caminho_base_obj())
        deformador = Deformador(malha)
        macros = ControladorMacros(deformador)
        inicio = macros.atualizar().copy()
        alterada = macros.definir_etnia("african", 0.75).copy()
        self.assertGreater(
            np.abs(inicio[:, :3] - alterada[:, :3]).max(), 0.001
        )
        np.testing.assert_array_equal(inicio[:, 6:8], alterada[:, 6:8])
        np.testing.assert_allclose(macros.restaurar(), inicio, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
