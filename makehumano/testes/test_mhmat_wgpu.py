"""Material .mhmat parcial: fixtures oficiais, paths seguros e valores."""

from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.acessorios import caminho_olhos_lowpoly, caminho_olhos_highpoly
from motor_wgpu.materiais_mhmat import (
    carregar_mhmat, material_referenciado, _arquivo_local,
)
from motor_wgpu.roupas import carregar_peca_externa
from motor_wgpu.malha import carregar_obj, caminho_base_obj


class TestarMaterialMHMat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpo = carregar_obj(caminho_base_obj())

    def test_material_real_olhos_resolve_diretorio_irmao(self):
        for caminho in (caminho_olhos_lowpoly(), caminho_olhos_highpoly()):
            with self.subTest(proxy=caminho.name):
                mhmat = material_referenciado(caminho)
                self.assertEqual(mhmat.name, "brown.mhmat")
                self.assertEqual(mhmat.parent.name, "materials")
                material = carregar_mhmat(mhmat)
                self.assertEqual(material.cor, (1.0, 1.0, 1.0))
                self.assertAlmostEqual(material.rugosidade, 0.25)
                self.assertTrue(material.textura.is_file())
                self.assertEqual(material.textura.name, "brown_eye.png")
                self.assertTrue(any("shader" in aviso for aviso in material.avisos))
                peca = carregar_peca_externa(caminho, self.corpo)
                self.assertEqual(peca.material, material)

    def test_material_sintetico_rgb_textura_e_rugosidade(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            textura = raiz / "tecido.png"
            textura.write_bytes(b"png-de-teste")
            material = raiz / "tecido.mhmat"
            material.write_text(
                "name Tecido azul\n"
                "diffuseColor 0.2 0.4 0.7\n"
                "diffuseTexture tecido.png\n"
                "shininess 0.4\n"
                "opacity 1.0\n"
                "shaderParam Custom ignored\n",
                encoding="utf-8",
            )
            resultado = carregar_mhmat(material)
            self.assertEqual(resultado.cor, (0.2, 0.4, 0.7))
            self.assertAlmostEqual(resultado.rugosidade, 0.70)
            self.assertEqual(resultado.textura, textura.resolve())
            self.assertTrue(resultado.avisos)

    def test_sem_material_usa_neutro(self):
        with tempfile.TemporaryDirectory() as pasta:
            proxy = Path(pasta) / "sem_material.mhclo"
            proxy.write_text(
                "obj_file roupa.obj\nverts 0\n0\n", encoding="utf-8"
            )
            self.assertIsNone(material_referenciado(proxy))

    def test_mhmat_rejeita_valores_malformados_sem_executar_instrucoes(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            arquivo = raiz / "material.mhmat"
            for texto, mensagem in (
                ("diffuseColor 0.2 nan 0.1", "diffuseColor"),
                ("diffuseColor 0.2 0.3", "RGB"),
                ("shininess -1.0", "shininess"),
                ("opacity 1.3", "opacity"),
                ("diffuseColor 1 1 1\ndiffuseColor 0 0 0", "duplicada"),
                ("diffuseTexture ../secreto.png", "não autorizado"),
                ("diffuseTexture /etc/passwd", "local"),
                ("diffuseTexture https://servidor/imagem.png", "URL"),
            ):
                with self.subTest(texto=texto):
                    arquivo.write_text(texto + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, mensagem):
                        carregar_mhmat(arquivo)

    def test_proxy_material_aceita_somente_irmao_materials(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            diretorio = raiz / "peca"
            diretorio.mkdir()
            (raiz / "materials").mkdir()
            (raiz / "materials" / "tecido.mhmat").write_text(
                "diffuseColor 1 1 1\n", encoding="utf-8"
            )
            proxy = diretorio / "roupa.mhclo"
            proxy.write_text(
                "material ../materials/tecido.mhmat\nverts 0\n0\n",
                encoding="utf-8",
            )
            self.assertEqual(
                material_referenciado(proxy),
                (raiz / "materials" / "tecido.mhmat").resolve(),
            )
            for referencia in (
                "../../passwd.mhmat", "../outra/segredo.mhmat",
                "C:/Windows/material.mhmat", "https://site/material.mhmat",
            ):
                with self.subTest(referencia=referencia):
                    proxy.write_text(
                        f"material {referencia}\nverts 0\n0\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        material_referenciado(proxy)

    def test_arquivo_sem_mhmat_nao_engana_importador(self):
        with tempfile.TemporaryDirectory() as pasta:
            proxy = Path(pasta) / "test.mhclo"
            proxy.write_text(
                "material estranho.py\nverts 0\n0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, ".mhmat"):
                material_referenciado(proxy)

    def test_transparencia_gera_aviso_nao_blending(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "transparente.mhmat"
            arquivo.write_text(
                "diffuseColor 1 1 1\nopacity 0.4\n",
                encoding="utf-8",
            )
            material = carregar_mhmat(arquivo)
            self.assertIn(
                "Transparência parcial não implementada no Vulkan",
                material.avisos,
            )


if __name__ == "__main__":
    unittest.main()
