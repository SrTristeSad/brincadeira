"""Máscaras de corpo/proxy contra regras da biblioteca MakeHuman original."""

import ast
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.mascaras import (
    GerenciadorMascaras, indices_corpo_visiveis, transferir_mascara_proxy,
)


def referencia_original():
    caminho = ROOT / "codigo/makehuman/shared/proxy.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    funcao = next(f for f in arvore.body if isinstance(f, ast.FunctionDef)
                  and f.name == "transferVertexMaskToProxy")
    modulo = ast.Module(body=[funcao], type_ignores=[])
    ast.fix_missing_locations(modulo)
    contexto = {"np": np}
    exec(compile(modulo, str(caminho), "exec"), contexto)
    return contexto["transferVertexMaskToProxy"]


class TestarMascaras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.malha = carregar_obj(caminho_base_obj())

    def test_mask_de_corpo_mantem_ordem_topologia_uv(self):
        malha = self.malha
        apagados = np.zeros(len(malha.posicoes_base), dtype=bool)
        np.testing.assert_array_equal(
            indices_corpo_visiveis(malha, apagados), malha.indices
        )
        vertice = int(malha.origens[malha.indices[0]])
        apagados[vertice] = True
        filtrados = indices_corpo_visiveis(malha, apagados)
        self.assertLess(len(filtrados), len(malha.indices))
        self.assertEqual(len(filtrados) % 3, 0)
        presentes = malha.origens[filtrados.reshape(-1, 3)]
        self.assertFalse(np.any(apagados[presentes]))
        # Não tocamos na estrutura original, importante para os morph targets.
        self.assertEqual(malha.indices[0], self.malha.indices[0])
        apagados[:] = True
        self.assertEqual(len(indices_corpo_visiveis(malha, apagados)), 0)

    def test_mask_corpo_valida_formato(self):
        malha = self.malha
        with self.assertRaises(ValueError):
            indices_corpo_visiveis(
                malha, np.zeros(len(malha.posicoes_base), dtype=np.float32)
            )
        with self.assertRaises(ValueError):
            indices_corpo_visiveis(malha, np.zeros(12, dtype=bool))

    def test_acessorios_visiveis_combinam_mascaras_sem_desgaste(self):
        malha = self.malha
        total = len(malha.posicoes_base)
        primeiro = np.zeros(total, dtype=bool)
        segundo = np.zeros(total, dtype=bool)
        primeiro[int(malha.origens[malha.indices[0]])] = True
        segundo[int(malha.origens[malha.indices[-1]])] = True
        gerenciador = GerenciadorMascaras(total)
        gerenciador.registrar("camisa", primeiro)
        gerenciador.registrar("calca", segundo, visivel=False)
        np.testing.assert_array_equal(gerenciador.combinada(), primeiro)
        self.assertEqual(
            len(indices_corpo_visiveis(malha, gerenciador.combinada())),
            len(indices_corpo_visiveis(malha, primeiro)),
        )

        # O chamador não pode alterar a máscara já registrada.
        primeiro[:] = False
        self.assertTrue(gerenciador.combinada().any())

        gerenciador.definir_visibilidade("calca", True)
        esperado = np.logical_or(primeiro, segundo)
        esperado[int(malha.origens[malha.indices[0]])] = True
        np.testing.assert_array_equal(gerenciador.combinada(), esperado)
        gerenciador.definir_visibilidade("camisa", False)
        np.testing.assert_array_equal(gerenciador.combinada(), segundo)
        gerenciador.definir_visibilidade("calca", False)
        self.assertFalse(gerenciador.combinada().any())
        gerenciador.definir_visibilidade("camisa", True)
        self.assertTrue(gerenciador.combinada().any())
        gerenciador.remover("camisa")
        self.assertFalse(gerenciador.combinada().any())

    def test_mascara_pode_ser_substituida_e_removida(self):
        manager = GerenciadorMascaras(8)
        manager.registrar("olhos")
        self.assertFalse(manager.combinada().any())
        mask = np.zeros(8, dtype=bool)
        mask[[1, 3]] = True
        manager.definir_mascara("olhos", mask)
        mask[:] = False
        np.testing.assert_array_equal(
            np.flatnonzero(manager.combinada()), [1, 3]
        )
        manager.definir_mascara("olhos", None)
        self.assertFalse(manager.combinada().any())

    def test_gerenciador_recusa_mascaras_e_nomes_invalidos(self):
        with self.assertRaises(ValueError):
            GerenciadorMascaras(0)
        manager = GerenciadorMascaras(7)
        with self.assertRaises(ValueError):
            manager.registrar("", np.zeros(7, dtype=bool))
        with self.assertRaises(ValueError):
            manager.registrar("roupa", np.zeros(4, dtype=bool))
        with self.assertRaises(ValueError):
            manager.registrar("roupa", np.ones(7, dtype=np.float32))
        manager.registrar("roupa")
        with self.assertRaises(ValueError):
            manager.registrar("roupa")
        with self.assertRaises(KeyError):
            manager.definir_visibilidade("inexistente", True)
        with self.assertRaises(KeyError):
            manager.definir_mascara("inexistente", None)
        with self.assertRaises(KeyError):
            manager.remover("inexistente")
        self.assertFalse(manager.combinada().any())

    def test_transferencia_mascara_equivalente_original(self):
        original = referencia_original()
        rng = np.random.default_rng(2026)
        for n in (1, 16, 512):
            for _ in range(4):
                visiveis = rng.choice([False, True], size=20)
                refs = rng.integers(0, 20, size=(n, 3), dtype=np.uint32)
                pesos = rng.normal(size=(n, 3)).astype(np.float32)
                pesos[::3, 1:] = 0
                classe_proxy = type("ProxyFake", (), {})
                proxy = classe_proxy()
                proxy.ref_vIdxs = refs
                proxy.weights = pesos
                esperado = original(visiveis, proxy)
                calculado = transferir_mascara_proxy(visiveis, refs, pesos)
                np.testing.assert_array_equal(calculado, esperado)

    def test_transferencia_mascara_rejeita_dados_inconsistentes(self):
        visivel = np.ones(6, dtype=bool)
        refs = np.array([[0, 1, 2]], np.uint32)
        pesos = np.array([[1.0, 0.0, 0.0]], np.float32)
        with self.assertRaises(ValueError):
            transferir_mascara_proxy(visivel, refs, np.ones((1, 2)))
        with self.assertRaises(ValueError):
            transferir_mascara_proxy(visivel, np.array([[0, 1, 7]]), pesos)
        with self.assertRaises(ValueError):
            transferir_mascara_proxy(visivel.astype(np.uint8), refs, pesos)


if __name__ == "__main__":
    unittest.main()
