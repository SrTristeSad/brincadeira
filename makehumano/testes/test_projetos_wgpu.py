"""Regressões do formato MakeHumano experimental para salvar personagens."""

from copy import deepcopy
from pathlib import Path
import json
import sys
import numpy as np
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.macro import PerfilMacro
from motor_wgpu.materiais import Pele
from motor_wgpu.modificadores import carregar_catalogo
from test_materiais_exportar_wgpu import decodificar_png_simples

from motor_wgpu.projetos import (
    FORMATO, VERSAO, montar_documento, salvar_documento,
    carregar_documento, validar_documento,
    salvar_projeto_com_texturas, carregar_texturas_projeto,
    pasta_texturas,
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
        pele = Pele(cor=(0.6, 0.4, 0.3), rugosidade=0.4, dispersao=0.68)
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
            self.assertAlmostEqual(aberto["pele"]["dispersao"], 0.68)

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

    def test_projeto_v1_abre_sem_mudar_aparencia_antiga(self):
        legado = self.exemplo()
        legado["versao"] = 1
        del legado["pele"]["dispersao"]
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "legado.makehumano.json"
            arquivo.write_text(json.dumps(legado), encoding="utf-8")
            migrado = carregar_documento(arquivo, self.catalogo)
            self.assertEqual(migrado["versao"], VERSAO)
            # Projetos antigos não tinham dispersão, portanto nenhum efeito.
            self.assertEqual(migrado["pele"]["dispersao"], 0.0)
            self.assertEqual(migrado["macros"], legado["macros"])
            self.assertEqual(migrado["modificadores"], legado["modificadores"])
            salvar_documento(arquivo, migrado, self.catalogo)
            self.assertEqual(
                json.loads(arquivo.read_text(encoding="utf-8"))["versao"], VERSAO
            )

    def test_dispersao_valida_limites_e_rejeita_invalidos(self):
        original = self.exemplo()
        for valor in (0, 0.33, 1):
            p = deepcopy(original)
            p["pele"]["dispersao"] = valor
            self.assertAlmostEqual(
                validar_documento(p, self.catalogo)["pele"]["dispersao"], valor
            )
        for valor in (-0.1, 1.1, float("nan"), float("inf"), True, "0.5"):
            p = deepcopy(original)
            p["pele"]["dispersao"] = valor
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                validar_documento(p, self.catalogo)

    def test_arquivo_json_invalido_e_tamanho_excessivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalid.makehumano.json"
            arquivo.write_text("{ json quebrado", encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_documento(arquivo, self.catalogo)
            arquivo.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "1 MB"):
                carregar_documento(arquivo, self.catalogo)

    def test_projeto_v2_migra_sem_texturas_externas(self):
        legado = self.exemplo()
        legado["versao"] = 2
        del legado["texturas"]
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta) / "versao2.makehumano.json"
            projeto.write_text(json.dumps(legado), encoding="utf-8")
            resultado = carregar_documento(projeto, self.catalogo)
            self.assertEqual(resultado["versao"], VERSAO)
            self.assertTrue(all(v is None for v in resultado["texturas"].values()))
            self.assertAlmostEqual(resultado["pele"]["dispersao"], 0.68)

    def test_roundtrip_de_imagens_png_gera_pasta_portatil(self):
        documento = self.exemplo()
        cor = np.array([
            [[10, 22, 33, 255], [44, 55, 66, 128]],
            [[77, 88, 99, 255], [15, 25, 35, 255]],
        ], dtype=np.uint8)
        normal = np.tile(np.array([150, 100, 245, 255], dtype=np.uint8), (2, 3, 1))
        imagens = {"cor": cor, "normal": normal, "rugosidade": None}

        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta) / "meu-personagem.makehumano.json"
            salvar_projeto_com_texturas(projeto, documento, self.catalogo, imagens)
            aberto = carregar_documento(projeto, self.catalogo)
            self.assertEqual(aberto["versao"], VERSAO)
            self.assertIsNone(aberto["texturas"]["rugosidade"])
            pasta_assets = pasta_texturas(projeto)
            self.assertTrue(pasta_assets.is_dir())
            self.assertEqual(
                set(p.name for p in pasta_assets.iterdir()),
                set(n for n in aberto["texturas"].values() if n is not None),
            )
            lidas = carregar_texturas_projeto(
                projeto, aberto, decodificar_png_simples
            )
            np.testing.assert_array_equal(lidas["cor"], cor)
            np.testing.assert_array_equal(lidas["normal"], normal)
            self.assertIsNone(lidas["rugosidade"])
            self.assertEqual(aberto["modificadores"], documento["modificadores"])

            # Conteúdo igual recebe os mesmos nomes; conteúdos diferentes
            # criam novas versões sem apagar as texturas antigas.
            salvar_projeto_com_texturas(projeto, documento, self.catalogo, imagens)
            self.assertEqual(len(list(pasta_assets.iterdir())), 2)
            segunda = cor.copy()
            segunda[0, 0, 0] = 99
            imagens["cor"] = segunda
            salvar_projeto_com_texturas(projeto, documento, self.catalogo, imagens)
            self.assertEqual(len(list(pasta_assets.iterdir())), 3)
            lidas = carregar_texturas_projeto(
                projeto, carregar_documento(projeto, self.catalogo),
                decodificar_png_simples,
            )
            np.testing.assert_array_equal(lidas["cor"], segunda)

    def test_projeto_recusa_caminhos_fora_da_pasta_e_dados_corrompidos(self):
        documento = self.exemplo()
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta) / "seguro.makehumano.json"
            imagens = {
                "cor": np.full((2, 2, 4), 255, dtype=np.uint8),
                "normal": None, "rugosidade": None,
            }
            for invalido in (
                "../../fora.png", "/tmp/segredo.png", "cor-123.png",
                "normal-" + "0" * 20 + ".png",
            ):
                teste = deepcopy(documento)
                teste["texturas"]["cor"] = invalido
                with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                    validar_documento(teste, self.catalogo)

            salvar_projeto_com_texturas(projeto, documento, self.catalogo, imagens)
            validado = carregar_documento(projeto, self.catalogo)
            imagem = pasta_texturas(projeto) / validado["texturas"]["cor"]
            imagem.write_bytes(b"arquivo-corrompido")
            with self.assertRaises(Exception):
                carregar_texturas_projeto(
                    projeto, validado, decodificar_png_simples
                )

            imagem.unlink()
            with self.assertRaises(OSError):
                carregar_texturas_projeto(
                    projeto, validado, decodificar_png_simples
                )

    def test_textura_invalida_nao_altera_projeto_existente(self):
        doc = self.exemplo()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "existente.makehumano.json"
            imagens = {"cor": np.full((3, 3, 4), 255, dtype=np.uint8),
                       "normal": None, "rugosidade": None}
            salvar_projeto_com_texturas(caminho, doc, self.catalogo, imagens)
            json_anterior = caminho.read_bytes()
            imagens["normal"] = np.zeros((2, 2, 3), dtype=np.uint8)
            with self.assertRaisesRegex(ValueError, "RGBA"):
                salvar_projeto_com_texturas(
                    caminho, doc, self.catalogo, imagens
                )
            self.assertEqual(caminho.read_bytes(), json_anterior)

    def test_documento_usa_identificadores_oficiais_sem_caminhos_externos(self):
        projeto = self.exemplo()
        self.assertEqual(set(projeto), {"formato", "versao", "macros", "etnias", "modificadores", "pele", "texturas"})
        self.assertEqual(len(projeto["modificadores"]), 2)
        self.assertTrue(all("data/targets" not in chave for chave in projeto["modificadores"]))


if __name__ == "__main__":
    unittest.main()
