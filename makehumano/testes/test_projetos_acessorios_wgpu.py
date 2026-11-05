"""Snapshots portáteis de acessórios com textura, visibilidade e máscaras."""

from copy import deepcopy
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.modificadores import carregar_catalogo
from motor_wgpu.materiais import Pele, textura_neutra
from motor_wgpu.macro import PerfilMacro
from motor_wgpu.projetos import (
    VERSAO, montar_documento, validar_documento, carregar_documento,
    salvar_projeto_com_texturas, pasta_texturas,
)
from motor_wgpu.projetos_acessorios import (
    carregar_acessorios_projeto, salvar_acessorios_projeto,
)
from motor_wgpu.roupas import carregar_peca_externa
from motor_wgpu.acessorios import caminho_olhos_highpoly
from test_roupas_wgpu import criar_proxy_externo
from test_materiais_exportar_wgpu import decodificar_png_simples


class TestarProjetosAcessorios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())
        cls.catalogo = carregar_catalogo()

    def documento(self):
        return montar_documento(
            PerfilMacro(), {}, Pele(dispersao=0.5), self.catalogo
        )

    @staticmethod
    def imagens_corpo():
        return {"cor": textura_neutra(), "normal": None, "rugosidade": None}

    def criar_peca(self, raiz, *, ponderado=True):
        arquivo = criar_proxy_externo(
            raiz, self.corpo, ponderado=ponderado,
            nome="peca" if ponderado else "simples"
        )
        peca = carregar_peca_externa(arquivo, self.corpo)
        pixels = np.tile(
            np.array([40, 110, 220, 255], dtype=np.uint8),
            (4, 6, 1),
        )
        return {
            "peca": peca,
            "pixels": pixels,
            "visivel": False,
            "cor": (0.27, 0.65, 0.84),
            "rugosidade": 0.43,
        }

    def test_persiste_peca_textura_mascara_cor_e_visibilidade(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            originais = raiz / "originais"
            originais.mkdir()
            item = self.criar_peca(originais)
            simples = self.criar_peca(originais, ponderado=False)
            simples["visivel"] = True
            destino = raiz / "modelo.makehumano.json"
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[item, simples],
            )
            doc = carregar_documento(destino, self.catalogo)
            self.assertEqual(doc["versao"], VERSAO)
            self.assertEqual(len(doc["acessorios"]), 2)
            self.assertFalse(doc["acessorios"][0]["visivel"])
            self.assertTrue(doc["acessorios"][1]["visivel"])
            self.assertEqual(doc["acessorios"][0]["cor"], list(item["cor"]))
            self.assertAlmostEqual(doc["acessorios"][0]["rugosidade"], 0.43)

            # Provar portabilidade: nenhum caminho depende mais dos originais.
            shutil.rmtree(originais)
            carregados = carregar_acessorios_projeto(
                destino, doc, self.corpo, decodificar_png_simples
            )
            self.assertEqual(len(carregados), 2)
            for esperado, obtido in zip((item, simples), carregados):
                np.testing.assert_array_equal(
                    obtido["pixels"], esperado["pixels"],
                )
                self.assertEqual(obtido["visivel"], esperado["visivel"])
                self.assertEqual(obtido["cor"], esperado["cor"])
                self.assertAlmostEqual(
                    obtido["rugosidade"], esperado["rugosidade"],
                )
                self.assertEqual(
                    obtido["peca"].tipo, esperado["peca"].tipo
                )
                np.testing.assert_allclose(
                    obtido["peca"].atualizar(self.corpo.posicoes_base),
                    esperado["peca"].atualizar(self.corpo.posicoes_base),
                    atol=2e-5, rtol=1e-5,
                )
            np.testing.assert_array_equal(
                carregados[0]["peca"].deletar_vertices,
                item["peca"].deletar_vertices,
            )
            assets = pasta_texturas(destino) / "acessorios"
            self.assertEqual(len(list(assets.iterdir())), 2)
            for diretorio in assets.iterdir():
                self.assertEqual(
                    {a.name for a in diretorio.iterdir()},
                    {"proxy.mhclo", "malha.obj", "textura.png"},
                )
                self.assertIn(
                    "obj_file malha.obj",
                    (diretorio / "proxy.mhclo").read_text(),
                )
                self.assertNotIn(
                    "material ",
                    (diretorio / "proxy.mhclo").read_text(),
                )

    def test_proxy_highpoly_original_fica_portatil_sem_mhmat_legado(self):
        """High-poly oficial usa offsets e material ../materials/ no original."""
        peca = carregar_peca_externa(caminho_olhos_highpoly(), self.corpo)
        self.assertIsNotNone(peca.material)
        pixels = np.full((4, 4, 4), 255, dtype=np.uint8)
        dados = {
            "peca": peca, "pixels": pixels, "visivel": True,
            "cor": peca.material.cor,
            "rugosidade": peca.material.rugosidade,
        }
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta) / "olhos.makehumano.json"
            salvar_projeto_com_texturas(
                projeto, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[dados],
            )
            documento = carregar_documento(projeto, self.catalogo)
            recuperado = carregar_acessorios_projeto(
                projeto, documento, self.corpo, decodificar_png_simples
            )[0]
            self.assertIsNone(recuperado["peca"].material)
            self.assertEqual(recuperado["peca"].tipo, "ponderado")
            self.assertEqual(len(recuperado["peca"].modelo.malha.posicoes_base), 1064)
            np.testing.assert_allclose(
                recuperado["peca"].atualizar(self.corpo.posicoes_base),
                peca.atualizar(self.corpo.posicoes_base),
                rtol=1e-5, atol=3e-5,
            )
            np.testing.assert_array_equal(recuperado["pixels"], pixels)

    def test_regravar_reutiliza_hash_e_aceita_peca_duplicada(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            item = self.criar_peca(raiz)
            destino = raiz / "duplo.makehumano.json"
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[item, item],
            )
            doc = carregar_documento(destino, self.catalogo)
            self.assertEqual(
                doc["acessorios"][0]["id"], doc["acessorios"][1]["id"]
            )
            self.assertEqual(len(list(
                (pasta_texturas(destino) / "acessorios").iterdir()
            )), 1)
            self.assertEqual(len(carregar_acessorios_projeto(
                destino, doc, self.corpo, decodificar_png_simples
            )), 2)

            imagem_nova = item["pixels"].copy()
            imagem_nova[0, 0, 0] ^= 0xFF
            novo_item = {**item, "pixels": imagem_nova}
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[novo_item],
            )
            self.assertEqual(len(list(
                (pasta_texturas(destino) / "acessorios").iterdir()
            )), 2)

    def test_arquivo_danificado_falha_antes_de_retornar_pecas(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            item = self.criar_peca(raiz)
            destino = raiz / "seguro.makehumano.json"
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[item],
            )
            doc = carregar_documento(destino, self.catalogo)
            pasta_peca = (
                pasta_texturas(destino) / "acessorios"
                / doc["acessorios"][0]["id"]
            )
            arquivo = pasta_peca / "malha.obj"
            arquivo.write_bytes(arquivo.read_bytes() + b"\n# modificado")
            with self.assertRaisesRegex(ValueError, "corrompido"):
                carregar_acessorios_projeto(
                    destino, doc, self.corpo, decodificar_png_simples
                )

    def test_rejeita_dados_json_invalidos(self):
        doc = self.documento()
        modelo = {
            "id": "a" * 24, "visivel": True, "cor": [1, 0.3, 0.5],
            "rugosidade": 0.33,
        }
        para_testar = (
            {**modelo, "id": "../pastas"},
            {**modelo, "id": "/tmp/" + "a" * 24},
            {**modelo, "visivel": "sim"},
            {**modelo, "cor": [float("nan"), 0.4, 0.5]},
            {**modelo, "rugosidade": 0.0},
            {**modelo, "injetado": "bad"},
        )
        for item in para_testar:
            invalido = deepcopy(doc)
            invalido["acessorios"] = [item]
            with self.subTest(item=item), self.assertRaises(ValueError):
                validar_documento(invalido, self.catalogo)
        invalido = deepcopy(doc)
        invalido["acessorios"] = [modelo] * 25
        with self.assertRaisesRegex(ValueError, "24"):
            validar_documento(invalido, self.catalogo)

    def test_peca_invalida_preserva_json_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            item = self.criar_peca(raiz)
            destino = raiz / "salvo.makehumano.json"
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[item],
            )
            original = destino.read_bytes()
            invalido = {**item, "pixels": np.zeros((1, 2, 3), np.uint8)}
            with self.assertRaisesRegex(ValueError, "RGBA"):
                salvar_projeto_com_texturas(
                    destino, self.documento(), self.catalogo,
                    self.imagens_corpo(), acessorios=[invalido]
                )
            self.assertEqual(destino.read_bytes(), original)

    def test_link_simbolico_interno_e_recusado(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            item = self.criar_peca(raiz)
            destino = raiz / "teste.makehumano.json"
            salvar_projeto_com_texturas(
                destino, self.documento(), self.catalogo,
                self.imagens_corpo(), acessorios=[item],
            )
            doc = carregar_documento(destino, self.catalogo)
            base = pasta_texturas(destino) / "acessorios"
            p = base / doc["acessorios"][0]["id"]
            alvo = p / "malha.obj"
            nome = p / "original.obj"
            alvo.rename(nome)
            try:
                alvo.symlink_to(nome)
            except (OSError, NotImplementedError):
                self.skipTest("Ambiente não permite symlinks")
            with self.assertRaisesRegex(ValueError, "simbólicos"):
                carregar_acessorios_projeto(
                    destino, doc, self.corpo, decodificar_png_simples
                )


if __name__ == "__main__":
    unittest.main()
