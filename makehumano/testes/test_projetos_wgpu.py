"""Regressões do formato MakeHumano experimental para salvar personagens."""

from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.macro import PerfilMacro
from motor_wgpu.materiais import Pele
from motor_wgpu.modificadores import carregar_catalogo
from motor_wgpu.projetos import (
    FORMATO, VERSAO, montar_documento, salvar_documento,
    carregar_documento, validar_documento,
)


class TestarProjetos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = carregar_catalogo()

    def exemplo(self):
        perfil = PerfilMacro()
        perfil.definir("age", 0.6)
        perfil.definir("weight", 0.72)
        perfil.definir_etnia("asian", 0.55)
        pele = Pele(cor=(0.6, 0.4, 0.3), rugosidade=0.4)
        return montar_documento(
            perfil, {
                "nose/nose-scale-horiz-decr|incr": -35,
                "torso/torso-vshape-decr|incr": 80,
            }, pele, self.catalogo,
        )

    def test_roundtrip_persiste_macros_etnias_morphs_e_material(self):
        documento = self.exemplo()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "personagem.makehumano.json"
            salvar_documento(caminho, documento, self.catalogo)
            aberto = carregar_documento(caminho, self.catalogo)
            self.assertEqual(aberto, documento)
            self.assertEqual(json.loads(caminho.read_text())["formato"], FORMATO)
            self.assertEqual(aberto["versao"], VERSAO)
            self.assertAlmostEqual(sum(aberto["etnias"].values()), 1.0)

    def test_valida_modificadores_desconhecidos_e_limites(self):
        documento = self.exemplo()
        alteracoes = [
            ("modificadores", {"desconhecido": 1}),
            ("modificadores", {"nose/nose-scale-horiz-decr|incr": 120}),
            ("modificadores", {"nose/nose-scale-horiz-decr|incr": True}),
            ("etnias", {"african": 0.8, "asian": 0.7, "caucasian": 0.1}),
            ("pele", {"cor": [0.3, 1.2, 0.3], "rugosidade": 0.5}),
            ("macros", {"age": 0.1}),
        ]
        for campo, errado in alteracoes:
            with self.subTest(campo=campo, valor=errado):
                p = deepcopy(documento)
                p[campo] = errado
                with self.assertRaises(ValueError):
                    validar_documento(p, self.catalogo)

    def test_nao_aceita_outro_formato_ou_valores_nao_finitos(self):
        modelo = self.exemplo()
        for chave, valor in [("versao", 999), ("formato", "mhm")]:
            invalido = deepcopy(modelo)
            invalido[chave] = valor
            with self.assertRaises(ValueError):
                validar_documento(invalido, self.catalogo)
        invalido = deepcopy(modelo)
        invalido["macros"]["weight"] = float("nan")
        with self.assertRaises(ValueError):
            validar_documento(invalido, self.catalogo)

    def test_arquivo_json_invalido_e_tamanho_excessivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalid.makehumano.json"
            arquivo.write_text("{ json quebrado", encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_documento(arquivo, self.catalogo)
            arquivo.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "1 MB"):
                carregar_documento(arquivo, self.catalogo)

    def test_documento_usa_identificadores_oficiais_sem_caminhos_externos(self):
        projeto = self.exemplo()
        self.assertEqual(set(projeto), {"formato", "versao", "macros", "etnias", "modificadores", "pele"})
        self.assertEqual(len(projeto["modificadores"]), 2)
        self.assertTrue(all("data/targets" not in chave for chave in projeto["modificadores"]))


if __name__ == "__main__":
    unittest.main()
