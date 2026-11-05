"""Importação MHM baseada em Human.load/save e nas definições do original."""

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.mhm import carregar_mhm, _mapa_macros
from motor_wgpu.modificadores import carregar_catalogo, PASTA_MODIFICADORES
from motor_wgpu.projetos import VERSAO, validar_documento
from motor_wgpu.macro import PerfilMacro


class TestarMHM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = carregar_catalogo()

    def arquivo(self, texto):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        caminho = Path(temp.name) / "personagem.mhm"
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def test_catalogo_249_modificadores_originais_todos_identificados(self):
        blocos = json.loads(
            (PASTA_MODIFICADORES / "modeling_modifiers.json").read_text(encoding="utf-8")
        )
        nomes_originais = set()
        for bloco in blocos:
            for mod in bloco["modifiers"]:
                if "macrovar" in mod:
                    nome = mod["macrovar"]
                else:
                    nome = mod["target"]
                    if mod.get("min") and mod.get("max"):
                        nome += "-" + mod["min"] + "|" + mod["max"]
                        if mod.get("mid"):
                            # O MakeHuman posiciona mid entre min e max.
                            nome = mod["target"] + "-" + mod["min"] + "|" + mod["mid"] + "|" + mod["max"]
                nomes_originais.add(f'{bloco["group"]}/{nome}')
        suportados = {m.identificador for m in self.catalogo} | set(
            _mapa_macros(PASTA_MODIFICADORES)
        )
        self.assertEqual(len(nomes_originais), 249)
        self.assertEqual(len(suportados), 249)
        self.assertEqual(nomes_originais, suportados)

    def test_leitura_mhm_salvo_pelo_makehuman(self):
        origem = self.arquivo(
            "# Written by MakeHuman v1.2.0\n"
            "version v1.2.0\n"
            "uuid 1e00d5b3\n"
            "name Personagem de teste\n"
            "tags teste;figura\n"
            "camera 0.000000 0.000000 0.000000 0.000000 0.000000 1.000000\n"
            "modifier macrodetails/Gender 0.700000\n"
            "modifier macrodetails/Age 0.650000\n"
            "modifier macrodetails-universal/Muscle 0.800000\n"
            "modifier macrodetails-universal/Weight 0.300000\n"
            "modifier macrodetails/African 0.600000\n"
            "modifier macrodetails/Asian 0.200000\n"
            "modifier macrodetails/Caucasian 0.200000\n"
            "modifier nose/nose-scale-horiz-decr|incr -0.370000\n"
            "modifier torso/torso-vshape-decr|incr 0.660000\n"
            "subdivide False\n"
        )
        resultado = carregar_mhm(origem, self.catalogo)
        doc = resultado.documento
        self.assertEqual(doc["versao"], VERSAO)
        self.assertEqual(doc["modificadores"]["nose/nose-scale-horiz-decr|incr"], -37)
        self.assertEqual(doc["modificadores"]["torso/torso-vshape-decr|incr"], 66)
        self.assertEqual(doc["macros"]["gender"], 0.7)
        self.assertEqual(doc["macros"]["age"], 0.65)
        self.assertEqual(doc["macros"]["muscle"], 0.8)
        self.assertEqual(doc["macros"]["weight"], 0.3)
        self.assertAlmostEqual(doc["etnias"]["african"], 0.6)
        self.assertAlmostEqual(doc["etnias"]["asian"], 0.2)
        self.assertEqual(resultado.modificadores_lidos, 9)
        self.assertEqual(resultado.modificadores_aplicados, 9)
        self.assertTrue(any("camera" in aviso for aviso in resultado.avisos))
        self.assertTrue(all(v is None for v in doc["texturas"].values()))
        self.assertEqual(doc["pele"]["dispersao"], 0)
        self.assertEqual(validar_documento(doc, self.catalogo), doc)

    def test_arquivo_mhm_com_todos_os_modificadores_suportados(self):
        linhas = ["version v1.2.0"]
        for m in self.catalogo:
            linhas.append(f"modifier {m.identificador} 0.000000")
        for nome in _mapa_macros(PASTA_MODIFICADORES):
            valor = 0.333333 if nome in (
                "macrodetails/African", "macrodetails/Asian", "macrodetails/Caucasian"
            ) else 0.5
            linhas.append(f"modifier {nome} {valor:.6f}")
        resultado = carregar_mhm(self.arquivo("\n".join(linhas)), self.catalogo)
        self.assertEqual(resultado.modificadores_aplicados, 249)
        self.assertEqual(resultado.modificadores_lidos, 249)
        self.assertEqual(resultado.documento["macros"], PerfilMacro().valores)
        self.assertAlmostEqual(sum(resultado.documento["etnias"].values()), 1)
        self.assertFalse(resultado.documento["modificadores"])

    def test_nao_ignora_incompatibilidades_silenciosamente(self):
        resultado = carregar_mhm(self.arquivo(
            "version v1.1.0\n"
            "modifier nose/nose-scale-horiz-decr|incr 0.125000\n"
            "modifier plugin/modificador-desconhecido 0.5\n"
            "material arquivo.mhmat\n"
            "clothes sapato.mhclo\n"
            "subdivide True\n"
        ), self.catalogo)
        self.assertEqual(resultado.documento["modificadores"]["nose/nose-scale-horiz-decr|incr"], 12)
        self.assertEqual(resultado.modificadores_aplicados, 1)
        avisos = "\n".join(resultado.avisos)
        self.assertIn("arredondado", avisos)
        self.assertIn("sem suporte", avisos)
        self.assertIn("material", avisos)
        self.assertIn("clothes", avisos)
        self.assertIn("subdivide", avisos)
        self.assertIn("conversões", avisos)

    def test_etnias_normalizadas_como_human_load(self):
        resultado = carregar_mhm(self.arquivo(
            "modifier macrodetails/African 0.900000\n"
            "modifier macrodetails/Asian 0.900000\n"
            "modifier macrodetails/Caucasian 0.000000\n"
        ), self.catalogo)
        self.assertAlmostEqual(resultado.documento["etnias"]["african"], 0.5)
        self.assertAlmostEqual(resultado.documento["etnias"]["asian"], 0.5)
        self.assertEqual(resultado.documento["etnias"]["caucasian"], 0)
        # O Human original reinicializa todos os valores se forem zero.
        zeros = carregar_mhm(self.arquivo(
            "modifier macrodetails/African 0\n"
            "modifier macrodetails/Asian 0\n"
            "modifier macrodetails/Caucasian 0\n"
        ), self.catalogo)
        for valor in zeros.documento["etnias"].values():
            self.assertAlmostEqual(valor, 1/3)

    def test_rejeita_numeros_invalidos_sem_aplicar(self):
        for s in (
            "modifier macrodetails/Gender nan",
            "modifier macrodetails/Gender -0.1",
            "modifier nose/nose-scale-horiz-decr|incr 1.2",
            "modifier nose/nose-scale-horiz-decr|incr nonsense",
            "modifier nose/nose-scale-horiz-decr|incr",
        ):
            with self.subTest(s=s), self.assertRaises(ValueError):
                carregar_mhm(self.arquivo(s), self.catalogo)

    def test_identificador_repetido_usa_ultima_linha(self):
        resultado = carregar_mhm(self.arquivo(
            "modifier nose/nose-scale-horiz-decr|incr 0.200000\n"
            "modifier nose/nose-scale-horiz-decr|incr -0.150000\n"
        ), self.catalogo)
        self.assertEqual(resultado.documento["modificadores"]["nose/nose-scale-horiz-decr|incr"], -15)
        self.assertTrue(any("repetido" in s for s in resultado.avisos))


if __name__ == "__main__":
    unittest.main()
