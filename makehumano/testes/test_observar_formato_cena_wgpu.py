"""Testes CPU do observador de captura; não exigem Qt/Vulkan nem GPU."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from observar_formato_cena_vulkan import observar_captura_offscreen


class ContextoFalso:
    def get_preferred_format(self, adapter):
        return "bgra8unorm-srgb"


class TexturaFalsa:
    def __init__(self, formato):
        self.format = formato


class CenaFalsa:
    contexto = ContextoFalso()
    adapter = object()
    formato = "bgra8unorm-srgb"

    def framebuffer_offscreen(self, largura, altura, *, formato=None):
        return TexturaFalsa(formato or self.formato)


class TestarObservacaoDeCena(unittest.TestCase):
    def test_captura_real_e_restauracao_do_metodo(self):
        cena = CenaFalsa()
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "evidencias" / "phong.json"
            with observar_captura_offscreen(cena, destino):
                textura = cena.framebuffer_offscreen(1024, 768)
            self.assertEqual(textura.format, "bgra8unorm-srgb")
            self.assertNotIn("framebuffer_offscreen", cena.__dict__)
            dados = json.loads(destino.read_text(encoding="utf-8"))
            self.assertEqual(dados["formato_cena_inicial"], "bgra8unorm-srgb")
            self.assertEqual(dados["formato_preferido_superficie"], "bgra8unorm-srgb")
            self.assertTrue(dados["observou_captura_offscreen"])
            self.assertTrue(dados["captura_concluida_sem_excecao"])
            self.assertTrue(dados["captura_1024x768_observada"])
            self.assertEqual(dados["estado"], "OBSERVADO")
            self.assertEqual(dados["texturas_offscreen_observadas"], [{
                "largura": 1024,
                "altura": 768,
                "formato_requisitado": None,
                "formato_cena_no_instante": "bgra8unorm-srgb",
                "formato_real_da_textura": "bgra8unorm-srgb",
            }])

    def test_sem_chamada_nao_afirma_captura(self):
        with tempfile.TemporaryDirectory() as pasta:
            cena = CenaFalsa()
            destino = Path(pasta) / "vazio.json"
            with observar_captura_offscreen(cena, destino):
                pass
            dados = json.loads(destino.read_text(encoding="utf-8"))
            self.assertFalse(dados["observou_captura_offscreen"])
            self.assertEqual(dados["texturas_offscreen_observadas"], [])
            self.assertFalse(dados["captura_1024x768_observada"])
            self.assertEqual(dados["estado"], "NAO_OBSERVADO")

    def test_excecao_restaura_metodo_e_registra_falha(self):
        with tempfile.TemporaryDirectory() as pasta:
            cena = CenaFalsa()
            destino = Path(pasta) / "falha.json"
            with self.assertRaisesRegex(RuntimeError, "erro propositado"):
                with observar_captura_offscreen(cena, destino):
                    cena.framebuffer_offscreen(320, 200, formato="rgba8unorm")
                    raise RuntimeError("erro propositado")
            self.assertNotIn("framebuffer_offscreen", cena.__dict__)
            dados = json.loads(destino.read_text(encoding="utf-8"))
            self.assertFalse(dados["captura_concluida_sem_excecao"])
            self.assertFalse(dados["captura_1024x768_observada"])
            self.assertEqual(dados["estado"], "NAO_OBSERVADO")
            self.assertIn("erro propositado", dados["erro_da_captura"])
            self.assertEqual(dados["texturas_offscreen_observadas"][0]["formato_real_da_textura"], "rgba8unorm")

    def test_alvo_outro_tamanho_nao_homologa(self):
        with tempfile.TemporaryDirectory() as pasta:
            cena = CenaFalsa()
            destino = Path(pasta) / "tamanho-diferente.json"
            with observar_captura_offscreen(cena, destino):
                cena.framebuffer_offscreen(160, 120)
            dados = json.loads(destino.read_text(encoding="utf-8"))
            self.assertTrue(dados["observou_captura_offscreen"])
            self.assertFalse(dados["captura_1024x768_observada"])
            self.assertEqual(dados["estado"], "NAO_OBSERVADO")

    def test_cena_ausente_e_erro_explicito(self):
        with self.assertRaisesRegex(RuntimeError, "ausente"):
            with observar_captura_offscreen(None, "nunca-sera-criado.json"):
                pass


if __name__ == "__main__":
    unittest.main()
