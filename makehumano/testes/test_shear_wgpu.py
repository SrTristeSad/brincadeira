"""Shear/offsets de proxies contra TMatrix.matrixFromShear original."""

import ast
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "codigo/makehuman/core"))

from motor_wgpu.acessorios import carregar_proxy_ponderado
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.transformacoes_proxy import matriz_cisalhamento


def referencia_makehuman():
    caminho = RAIZ / "codigo/makehuman/shared/proxy.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    classe = next(c for c in arvore.body if isinstance(c, ast.ClassDef)
                  and c.name == "TMatrix")
    metodo = next(f for f in classe.body if isinstance(f, ast.FunctionDef)
                  and f.name == "matrixFromShear")
    utilitario = next(f for f in arvore.body if isinstance(f, ast.FunctionDef)
                      and f.name == "vertsToNumpy")
    modulo = ast.Module(body=[metodo, utilitario], type_ignores=[])
    ast.fix_missing_locations(modulo)
    namespace = {"np": np}
    exec(compile(modulo, str(caminho), "exec"), namespace)
    return namespace["matrixFromShear"]


class TestarShear(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())
        cls.original = staticmethod(referencia_makehuman())

    def entradas(self):
        corpo = self.corpo.posicoes_base
        # As escalas originais não precisam ser coordenadas do corpo,
        # e cada eixo precisa formar intervalo não degenerado.
        return (
            (5399, 11998, -1.1, 1.2),
            (791, 881, -1.5, 1.4),
            (962, 5320, -0.8, 1.0),
        )

    def test_matriz_shear_equivale_original_em_tres_malhas(self):
        original = self.original
        for variacao in (0, 1, 2):
            com = self.corpo.posicoes_base.copy()
            if variacao == 1:
                com[:, 0] *= 1.13
                com[:, 1] *= 0.93
            elif variacao == 2:
                com[:, 2] *= 1.2
                com[:, 1] += 0.1 * com[:, 0]
            entradas = self.entradas()
            esperado = original(None, entradas, com)
            resultado = matriz_cisalhamento(entradas, com)
            np.testing.assert_allclose(
                resultado, esperado, atol=2e-5, rtol=2e-5
            )
            self.assertTrue(np.isfinite(resultado).all())

    def test_parser_proxy_shear_mascara_e_geom_no_mesmo_arquivo(self):
        com = self.corpo.posicoes_base
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            (tmp / "roupa.obj").write_text(
                "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
                "vt 0 0\nvt 1 0\nvt 0 1\n"
                "f 1/1 2/2 3/3\n", encoding="utf-8"
            )
            shear = self.entradas()
            linhas = ["obj_file roupa.obj"]
            for eixo, item in zip("xyz", shear):
                linhas.append("shear_" + eixo + " " + " ".join(str(v) for v in item))
            linhas.extend([
                "verts 0",
                "0 1 2 0.25 0.50 0.25 0.1 0.2 -0.3",
                "0 1 2 0.25 0.50 0.25 -0.1 0.1 0.4",
                "0 1 2 0.25 0.50 0.25 0.2 -0.1 0.1",
                "delete_verts",
                "0 1 - 3 10",
            ])
            arquivo = tmp / "roupa.mhclo"
            arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
            proxy = carregar_proxy_ponderado(arquivo, self.corpo)
            self.assertIsNone(proxy.escalas)
            self.assertEqual(proxy.cisalhamento, shear)
            self.assertEqual(proxy.deletar_vertices.sum(), 5)
            np.testing.assert_array_equal(
                np.flatnonzero(proxy.deletar_vertices), [0, 1, 2, 3, 10]
            )
            resultado = proxy.atualizar(com)
            refs, pesos, offsets = proxy.referencias, proxy.pesos, proxy.deslocamentos
            referencia = self.original(None, shear, com)
            esperado = np.sum(com[refs] * pesos[:, :, None], axis=1)
            esperado += offsets @ referencia.T
            np.testing.assert_allclose(
                resultado[:, :3], esperado[proxy.malha.origens],
                rtol=1e-5, atol=2e-5
            )
            np.testing.assert_array_equal(
                resultado[:, 6:8], proxy.malha.vertices[:, 6:8]
            )

    def test_parser_rejeita_shear_parcial_e_intervalo_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            (tmp / "item.obj").write_text(
                "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
                "vt 0 0\nvt 1 0\nvt 0 1\n"
                "f 1/1 2/2 3/3\n", encoding="utf-8"
            )
            padrao = (
                "obj_file item.obj\n"
                "shear_x 0 1 -1 1\n"
                "verts 0\n"
                + "0 1 2 0.2 0.6 0.2 0 0 0\n" * 3
            )
            item = tmp / "item.mhclo"
            item.write_text(padrao, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incompleto"):
                carregar_proxy_ponderado(item, self.corpo)

            completo = padrao.replace(
                "verts 0\n",
                "shear_y 0 1 -1 1\nshear_z 0 1 -1 1\nverts 0\n",
            )
            for invalido in ("3 - 1", "0 -", "999999", "- 1"):
                with self.subTest(invalido=invalido):
                    item.write_text(
                        completo + "delete_verts\n" + invalido + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        carregar_proxy_ponderado(item, self.corpo)

    def test_matriz_shear_rejeita_caixa_degenerada(self):
        entradas = list(self.entradas())
        entradas[0] = (0, 1, 1.0, 1.0)
        with self.assertRaises(ValueError):
            matriz_cisalhamento(entradas, self.corpo.posicoes_base)


if __name__ == "__main__":
    unittest.main()
