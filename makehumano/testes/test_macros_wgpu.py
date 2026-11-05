"""Testes de macros contra os métodos originais de human.py.

As funções do MakeHuman são extraídas sintaticamente do próprio repositório
para evitar importar a aplicação Qt inteira nos testes. Nenhuma fórmula de
referência é reescrita aqui: a comparação usa os métodos _set*Vals originais.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.macro import (
    CATEGORIAS, ControladorMacros, PerfilMacro, arquivos_macro, fatores_alvo,
)
from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.morphs import Deformador


HUMAN_PY = RAIZ / "codigo" / "makehuman" / "apps" / "human.py"
METODOS = {
    "age": ("_setAgeVals", "age"),
    "gender": ("_setGenderVals", "gender"),
    "weight": ("_setWeightVals", "weight"),
    "muscle": ("_setMuscleVals", "muscle"),
    "height": ("_setHeightVals", "height"),
    "breastSize": ("_setBreastSizeVals", "breastsize"),
    "breastFirmness": ("_setBreastFirmnessVals", "breastfirmness"),
    "bodyProportions": ("_setBodyProportionVals", "bodyproportions"),
}


def obter_metodo_original(nome):
    arvore = ast.parse(HUMAN_PY.read_text(encoding="utf-8"))
    classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == "Human")
    metodo = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == nome)
    fragmento = ast.Module(body=[metodo], type_ignores=[])
    ast.fix_missing_locations(fragmento)
    namespace = {}
    exec(compile(fragmento, str(HUMAN_PY), "exec"), namespace)
    return namespace[nome]


class TestarMacros(unittest.TestCase):
    def test_todos_os_fatores_reproduzem_o_human_original(self):
        for chave, (metodo, categoria) in METODOS.items():
            original = obter_metodo_original(metodo)
            for valor in (0.0, 0.1, 0.1875, 0.25, 0.5, 0.6, 0.75, 1.0):
                with self.subTest(chave=chave, valor=valor):
                    exemplo = SimpleNamespace(**{chave: valor})
                    original(exemplo)
                    perfil = PerfilMacro()
                    perfil.definir(chave, valor)
                    obtidos = perfil.fatores()
                    for fator in CATEGORIAS[categoria]:
                        self.assertAlmostEqual(
                            obtidos[fator],
                            getattr(exemplo, fator + "Val"),
                            places=6,
                        )

    def test_default_e_probabilidades(self):
        f = PerfilMacro().fatores()
        self.assertEqual(f["young"], 1)
        self.assertEqual(f["old"], 0)
        self.assertAlmostEqual(f["male"] + f["female"], 1)
        self.assertAlmostEqual(f["averageweight"], 1)
        self.assertAlmostEqual(f["averagemuscle"], 1)
        self.assertAlmostEqual(f["caucasian"] + f["asian"] + f["african"], 1)
        p = PerfilMacro()
        with self.assertRaises(ValueError):
            p.definir("weight", float("nan"))
        with self.assertRaises(ValueError):
            p.definir("weight", -1)
        with self.assertRaises(KeyError):
            p.definir("inexistente", 0.4)

    def test_arquivos_macro_sao_reais_e_valores_padroes(self):
        arquivos = arquivos_macro()
        self.assertGreaterEqual(len(arquivos), 500)
        self.assertEqual(len(set(arquivos)), len(arquivos))
        self.assertTrue(all(a.exists() for a in arquivos))
        fatores = PerfilMacro().fatores()
        ativos = [arquivo for arquivo in arquivos if fatores_alvo(arquivo, fatores) > 0]
        self.assertGreaterEqual(len(ativos), 8)
        self.assertLess(len(ativos), len(arquivos) // 2)

    def test_pesos_multiplicam_genero_idade_musculo_e_peso(self):
        arquivo = next(
            a for a in arquivos_macro()
            if a.name == "universal-female-young-maxmuscle-maxweight.target"
        )
        p = PerfilMacro()
        p.definir("gender", 0.25)  # female: 0.75
        p.definir("muscle", 0.75)  # maxmuscle: 0.5
        p.definir("weight", 0.75)  # maxweight: 0.5
        self.assertAlmostEqual(fatores_alvo(arquivo, p.fatores()), 0.75 * 0.5 * 0.5)

    def test_atualizacao_de_macros_e_reversao_sem_perder_morph_direto(self):
        malha = carregar_obj(caminho_base_obj())
        deformador = Deformador(malha)
        controle = ControladorMacros(deformador)
        padrao = controle.atualizar().copy()
        alterado = controle.definir("muscle", 0.85).copy()
        self.assertGreater(np.max(np.abs(padrao[:, :3] - alterado[:, :3])), 0.001)
        np.testing.assert_allclose(controle.restaurar(), padrao, atol=1e-5)

        # Testa composição com um modificador direto e manutenção do efeito
        # ao mexer em uma macrovariável.
        from motor_wgpu.morphs import Alvo
        alvo = Alvo(
            indices=np.array([0], dtype=np.uint32),
            deslocamentos=np.array([[0.1, 0, 0]], dtype=np.float32),
        )
        com_direto = deformador.definir_peso("morph-direto", alvo, 1.0).copy()
        controle.definir("weight", 0.8)
        com_direto_novamente = controle.restaurar().copy()
        np.testing.assert_allclose(com_direto_novamente, com_direto, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
