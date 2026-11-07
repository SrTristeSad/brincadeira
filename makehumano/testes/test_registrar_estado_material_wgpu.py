"""Regressões do coletor de estado sem Qt, OpenGL ou Vulkan."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registrar_estado_material import descrever_material, salvar_estado


class TestarEstadoMaterial(unittest.TestCase):
    def _material(self, **extras):
        dados = {
            "name": "corpo",
            "shader": "/instalacao/data/shaders/glsl/phong",
            "shaderConfig": {"diffuse": True, "ambientOcclusion": False},
            "shaderDefines": ["DIFFUSE"],
            "shaderParameters": {"intensity": 0.5},
            "diffuseColor": SimpleNamespace(values=(0.3, 0.6, 0.9)),
            "diffuseTexture": None,
        }
        dados.update(extras)
        return SimpleNamespace(**dados)

    def test_config_define_e_cor_preservados(self):
        material = self._material()
        estado = descrever_material(material)
        self.assertTrue(estado["define_diffuse_ativo"])
        self.assertTrue(estado["shaderConfig"]["diffuse"])
        self.assertEqual(estado["shader"]["nome"], "phong")
        self.assertEqual(estado["diffuseColor"], [0.3, 0.6, 0.9])
        self.assertEqual(material.shaderDefines, ["DIFFUSE"])

    def test_define_nao_se_inventa_pela_config(self):
        material = self._material(shaderDefines=[])
        estado = descrever_material(material)
        self.assertFalse(estado["define_diffuse_ativo"])
        self.assertTrue(estado["shaderConfig"]["diffuse"])

    def test_hash_de_textura_real(self):
        with tempfile.TemporaryDirectory() as pasta:
            textura = Path(pasta) / "pele.png"
            textura.write_bytes(b"png-teste")
            estado = descrever_material(self._material(diffuseTexture=str(textura)))
            mapa = estado["mapas"]["diffuseTexture"]
            self.assertEqual(mapa["sha256"], hashlib.sha256(b"png-teste").hexdigest())
            self.assertEqual(mapa["nome"], "pele.png")
            self.assertTrue(mapa["existe"])

    def test_ausencia_de_arquivo_e_explicita(self):
        estado = descrever_material(
            self._material(diffuseTexture="/arquivo/inexistente/pele.png")
        )
        self.assertFalse(estado["mapas"]["diffuseTexture"]["existe"])
        self.assertNotIn("sha256", estado["mapas"]["diffuseTexture"])

    def test_salvar_nao_modifica_objeto_e_registra_luz(self):
        material = self._material()
        cena = SimpleNamespace(
            environment=SimpleNamespace(ambience=(0.1, 0.2, 0.3)),
            lights=[SimpleNamespace(position=(1, 2, 3), focus=(0, 0, 0))],
        )
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "estado.json"
            salvar_estado(caminho, material, cena, referencia="candidato")
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            self.assertEqual(dados["referencia"], "candidato")
            self.assertEqual(dados["iluminacao"]["ambiente"], [0.1, 0.2, 0.3])
            self.assertEqual(dados["iluminacao"]["luzes"][0]["position"], [1, 2, 3])
            self.assertEqual(material.shaderParameters["intensity"], 0.5)


if __name__ == "__main__":
    unittest.main()
