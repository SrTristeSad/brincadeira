"""Valida acessórios com ligação .mhclo original sem GPU ou Qt."""

from pathlib import Path
import sys
import ast
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motor_wgpu.acessorios import (
    carregar_proxy_direto, caminho_olhos_lowpoly,
    carregar_proxy_ponderado, caminho_olhos_highpoly,
)
from motor_wgpu.malha import caminho_base_obj, carregar_obj
from motor_wgpu.morphs import Deformador, Alvo


class TestarAcessorios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())
        cls.olhos = carregar_proxy_direto(caminho_olhos_lowpoly(), cls.corpo)
        cls.olhos_high = carregar_proxy_ponderado(
            caminho_olhos_highpoly(), cls.corpo
        )

    def test_malha_olhos_oficial_96_vertices_com_uvs(self):
        olhos = self.olhos
        self.assertEqual(len(olhos.referencias), 96)
        self.assertTrue(olhos.textura.is_file())
        self.assertGreater(len(olhos.malha.indices), 100)
        self.assertEqual(len(olhos.malha.indices) % 3, 0)
        np.testing.assert_array_equal(
            olhos.malha.posicoes_base,
            self.corpo.posicoes_base[olhos.referencias],
        )
        self.assertTrue(np.isfinite(olhos.malha.vertices).all())
        np.testing.assert_array_equal(
            olhos.atualizar(self.corpo.posicoes_base),
            olhos.malha.vertices,
        )

    def test_olhos_seguem_target_real_em_indices_do_corpo(self):
        corpo = self.corpo
        olhos = self.olhos
        vertice_base = int(olhos.referencias[0])
        alvo = Alvo(
            indices=np.array([vertice_base], dtype=np.uint32),
            deslocamentos=np.array([[0.06, -0.03, 0.12]], dtype=np.float32),
        )
        deformador = Deformador(corpo)
        primeira = olhos.atualizar(deformador.posicoes_atuais)
        deformador.definir_peso("mover-olho", alvo, 0.5)
        atual = olhos.atualizar(deformador.posicoes_atuais)
        indice_render = np.flatnonzero(olhos.malha.origens == 0)[0]
        np.testing.assert_allclose(
            atual[indice_render, :3] - primeira[indice_render, :3],
            [0.03, -0.015, 0.06], atol=1e-6,
        )
        np.testing.assert_array_equal(atual[:, 6:8], primeira[:, 6:8])
        self.assertFalse(np.array_equal(atual[:, 3:6], primeira[:, 3:6]))
        deformador.restaurar()
        np.testing.assert_allclose(
            olhos.atualizar(deformador.posicoes_atuais), primeira,
            atol=1e-6,
        )

    def test_highpoly_lido_do_proxy_oficial(self):
        olhos = self.olhos_high
        self.assertEqual(len(olhos.malha.posicoes_base), 1064)
        self.assertEqual(olhos.referencias.shape, (1064, 3))
        self.assertTrue(olhos.textura.is_file())
        self.assertEqual(len(olhos.escalas), 3)
        self.assertEqual(olhos.pesos.shape, (1064, 3))
        self.assertEqual(olhos.deslocamentos.shape, (1064, 3))
        self.assertTrue(np.any(olhos.deslocamentos != 0))
        self.assertTrue(np.any(olhos.pesos < 0))
        atual = olhos.atualizar(self.corpo.posicoes_base)
        self.assertTrue(np.isfinite(atual).all())
        np.testing.assert_array_equal(
            atual[:, 6:8], olhos.malha.vertices[:, 6:8],
        )
        # O OBJ high-poly contém posições que só passam à geometria certa
        # depois de aplicar a matriz de mapeamento do arquivo .mhclo.
        self.assertGreater(
            np.max(np.abs(atual[:, :3] - olhos.malha.vertices[:, :3])),
            0.1,
        )

    def test_highpoly_equivalente_a_proxy_getcoords_e_tmatrix_originais(self):
        """Executa métodos originais de shared/proxy.py sem importar a GUI."""
        caminho = (
            RAIZ / "codigo" / "makehuman" / "shared" / "proxy.py"
        )
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        def metodo(nome_classe, nome):
            classe = next(n for n in arvore.body
                          if isinstance(n, ast.ClassDef) and n.name == nome_classe)
            funcao = next(n for n in classe.body
                          if isinstance(n, ast.FunctionDef) and n.name == nome)
            mod = ast.Module(body=[funcao], type_ignores=[])
            ast.fix_missing_locations(mod)
            escopo = {"np": np}
            exec(compile(mod, str(caminho), "exec"), escopo)
            return escopo[nome]

        get_matrix = metodo("TMatrix", "getMatrix")
        get_coords = metodo("Proxy", "getCoords")
        olhos = self.olhos_high
        fake_tmatrix = SimpleNamespace(
            scaleData=list(olhos.escalas), shearData=None,
            lShearData=None, rShearData=None,
        )
        for perfil in (None, "simetrico", "assimetrico"):
            with self.subTest(perfil=perfil):
                deformador = Deformador(self.corpo)
                if perfil is not None:
                    idx = np.unique(olhos.referencias[:, 0])
                    desloc = np.zeros((len(idx), 3), dtype=np.float32)
                    desloc[:, 0] = (0.15 if perfil == "simetrico" else -0.12)
                    desloc[:, 1] = (0.04 if perfil == "simetrico" else -0.02)
                    desloc[:, 2] = 0.03
                    deformador.definir_peso(
                        "alterar-face", Alvo(idx, desloc), 1.0,
                    )
                corpo = deformador.posicoes_atuais
                original = SimpleNamespace(
                    ref_vIdxs=olhos.referencias,
                    weights=olhos.pesos,
                    offsets=olhos.deslocamentos,
                    tmatrix=SimpleNamespace(
                        getMatrix=lambda coords: get_matrix(fake_tmatrix, coords)
                    ),
                    human=SimpleNamespace(
                        getRestposeCoordinates=lambda: corpo
                    ),
                )
                esperado = get_coords(original)
                obtido = olhos.atualizar(corpo)
                np.testing.assert_allclose(
                    obtido[:, :3], esperado[olhos.malha.origens],
                    rtol=1e-5, atol=3e-5,
                )
                np.testing.assert_array_equal(
                    obtido[:, 6:8], olhos.malha.vertices[:, 6:8]
                )

    def test_proxy_ponderado_rejeita_escala_e_pesos_invalidos(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            (tmp / "item.obj").write_text(
                "v 0 0 0\\nv 1 0 0\\nv 0 1 0\\n"
                "vt 0 0\\nvt 1 0\\nvt 0 1\\n"
                "f 1/1 2/2 3/3\\n", encoding="utf-8",
            )
            prefixo = (
                "obj_file item.obj\\n"
                "x_scale 0 1 1\\ny_scale 0 1 1\\nz_scale 0 1 1\\n"
                "verts 0\\n"
            )
            caso = tmp / "item.mhclo"
            for invalido, mensagem in (
                ("0 1 2 nan 0 0 0 0 0", "não finito"),
                ("0 1 999999 0.3 0.3 0.4 0 0 0", "fora do corpo"),
                ("0 1 2 0.3 0.3 0.4", "três referências"),
                ("0 1 2 0.3 0.3 0.4 0 0 nope", "inválida"),
            ):
                with self.subTest(invalido=invalido):
                    caso.write_text(prefixo + invalido + "\\n" * 3, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, mensagem):
                        carregar_proxy_ponderado(caso, self.corpo)
            caso.write_text(
                prefixo.replace("x_scale 0 1 1", "x_scale 0 1 0")
                + "0 1 2 0.3 0.3 0.4 0 0 0\\n" * 3,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "escala fora"):
                carregar_proxy_ponderado(caso, self.corpo)

    def test_nao_confunde_proxy_complexo_com_mapeamento_direto(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            (tmp / "olho.obj").write_text(
                "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
                "vt 0 0\nvt 1 0\nvt 0 1\n"
                "f 1/1 2/2 3/3\n", encoding="utf-8",
            )
            proxy = tmp / "olho.mhclo"
            proxy.write_text(
                "obj_file olho.obj\nverts 0\n"
                "1 2 3 0.3 0.4 0.3 0 0 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "interpolado"):
                carregar_proxy_direto(proxy, self.corpo)

    def test_rejeita_indice_fora_do_corpo_e_caminho_externo(self):
        with tempfile.TemporaryDirectory() as pasta:
            tmp = Path(pasta)
            proxy = tmp / "estranho.mhclo"
            proxy.write_text(
                "obj_file ../segredo.obj\nverts 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "local"):
                carregar_proxy_direto(proxy, self.corpo)
            proxy.write_text(
                "obj_file olho.obj\nverts 0\n999999\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "fora do corpo"):
                carregar_proxy_direto(proxy, self.corpo)


if __name__ == "__main__":
    unittest.main()
