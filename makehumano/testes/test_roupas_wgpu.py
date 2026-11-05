"""Importação externa de proxies: geometria, máscaras e falhas explícitas."""

from pathlib import Path
import tempfile
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.morphs import Alvo, Deformador
from motor_wgpu.roupas import carregar_peca_externa, tipo_referencia_mhclo
from motor_wgpu.mascaras import indices_corpo_visiveis


def criar_proxy_externo(pasta, corpo, ponderado=True, *, nome="roupa"):
    """Cria asset sintético, sem fingir que é uma roupa MakeHuman oficial."""
    pasta = Path(pasta)
    posicoes = corpo.posicoes_base
    obj = pasta / (nome + ".obj")
    mhclo = pasta / (nome + ".mhclo")
    linhas = [
        "# malha sintética para regressão do motor WGPU",
        *("v " + " ".join(str(float(x)) for x in v) for v in posicoes[:3]),
        "vt 0 0", "vt 1 0", "vt 0 1", "f 1/1 2/2 3/3",
    ]
    obj.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    if ponderado:
        delete = int(corpo.origens[corpo.indices[0]])
        mhclo.write_text(
            "obj_file " + obj.name + "\n"
            "x_scale 5399 11998 1.6482\n"
            "y_scale 791 881 2.7213\n"
            "z_scale 962 5320 2.2795\n"
            "verts 0\n"
            "0 1 2 1 0 0 0 0 0\n"
            "0 1 2 0 1 0 0 0 0\n"
            "0 1 2 0 0 1 0 0 0\n"
            "delete_verts\n"
            + str(delete) + "\n",
            encoding="utf-8",
        )
    else:
        mhclo.write_text(
            "obj_file " + obj.name + "\nverts 0\n0\n1\n2\n",
            encoding="utf-8",
        )
    return mhclo


class TestarImportacaoExterna(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())

    def test_proxy_direto_externo_mantem_geometria(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = criar_proxy_externo(pasta, self.corpo, ponderado=False)
            self.assertEqual(tipo_referencia_mhclo(arquivo), "direto")
            peca = carregar_peca_externa(arquivo, self.corpo)
            self.assertEqual(peca.tipo, "direto")
            self.assertIsNone(peca.deletar_vertices)
            self.assertEqual(peca.origem, arquivo)
            normal = peca.atualizar(self.corpo.posicoes_base)
            np.testing.assert_allclose(
                normal[:, :3], peca.modelo.malha.vertices[:, :3], atol=1e-6
            )

    def test_proxy_ponderado_mascara_e_morph(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = criar_proxy_externo(pasta, self.corpo, ponderado=True)
            self.assertEqual(tipo_referencia_mhclo(arquivo), "ponderado")
            peca = carregar_peca_externa(arquivo, self.corpo)
            self.assertEqual(peca.tipo, "ponderado")
            self.assertEqual(int(peca.deletar_vertices.sum()), 1)
            self.assertLess(
                len(indices_corpo_visiveis(self.corpo, peca.deletar_vertices)),
                len(self.corpo.indices),
            )
            deformador = Deformador(self.corpo)
            primeiro = peca.atualizar(deformador.posicoes_atuais)
            alvo = Alvo(
                indices=np.array([0], dtype=np.uint32),
                deslocamentos=np.array([[0.2, 0.1, -0.3]], dtype=np.float32),
            )
            deformador.definir_peso("ajuste", alvo, 0.5)
            segundo = peca.atualizar(deformador.posicoes_atuais)
            np.testing.assert_allclose(
                segundo[0, :3] - primeiro[0, :3],
                [0.1, 0.05, -0.15], atol=1e-6,
            )
            np.testing.assert_array_equal(
                segundo[:, 6:8], primeiro[:, 6:8]
            )
            deformador.restaurar()
            np.testing.assert_allclose(
                peca.atualizar(deformador.posicoes_atuais), primeiro,
                atol=1e-6,
            )

    def test_arquivo_ou_proxies_nao_suportados_falham(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = criar_proxy_externo(pasta, self.corpo, ponderado=True)
            with self.assertRaisesRegex(ValueError, "\\.mhclo"):
                tipo_referencia_mhclo(arquivo.with_suffix(".obj"))
            original = arquivo.read_text(encoding="utf-8")
            arquivo.write_text(
                original.replace(
                    "0 1 2 1 0 0 0 0 0", "0 1 2 0.5 0.5"
                ), encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Apenas referências"):
                carregar_peca_externa(arquivo, self.corpo)
            arquivo.write_text(
                original.replace("obj_file roupa.obj", "obj_file ../fora.obj"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "OBJ local"):
                carregar_peca_externa(arquivo, self.corpo)
            arquivo.write_text(
                original.replace("x_scale", "unknown_scale"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "não suportada"):
                carregar_peca_externa(arquivo, self.corpo)


if __name__ == "__main__":
    unittest.main()
