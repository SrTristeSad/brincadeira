"""Máscaras de corpo/proxy contra regras da biblioteca MakeHuman original."""

import ast
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.mascaras import indices_corpo_visiveis, transferir_mascara_proxy


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
