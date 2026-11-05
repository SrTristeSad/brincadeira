"""OBJ exportado deve manter forma, UVs, índices e deformações MakeHuman."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.exportar import exportar_obj
from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.morphs import Deformador, ler_target, pasta_targets


class TestarExportacaoOBJ(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.malha = carregar_obj(caminho_base_obj())

    def test_exporta_cabeca_deformada_e_reimporta_com_mesmas_uvs(self):
        malha = self.malha
        deformador = Deformador(malha)
        alvo = ler_target(
            pasta_targets() / "nose" / "nose-scale-horiz-incr.target",
            len(malha.posicoes_base),
        )
        dados = deformador.definir_peso("nariz", alvo, 0.75).copy()
        self.assertGreater(
            np.max(np.abs(dados[:, :3] - malha.vertices[:, :3])), 0.001,
        )
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "personagem.obj"
            self.assertEqual(exportar_obj(arquivo, malha, dados), arquivo)
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
            self.assertEqual(sum(s.startswith("v ") for s in linhas),
                             len(malha.posicoes_base))
            self.assertEqual(sum(s.startswith("vt ") for s in linhas),
                             len(malha.vertices))
            self.assertEqual(sum(s.startswith("vn ") for s in linhas),
                             len(malha.vertices))
            self.assertEqual(sum(s.startswith("f ") for s in linhas),
                             len(malha.indices) // 3)
            reimportada = carregar_obj(arquivo)
            # Mesmo índice OBJ e a mesma ordem de vértices renderizados.
            np.testing.assert_array_equal(reimportada.origens, malha.origens)
            np.testing.assert_array_equal(reimportada.indices, malha.indices)
            canonic_pos = malha.posicoes_base.copy()
            canonic_pos[malha.origens] = dados[:, :3]
            np.testing.assert_array_equal(reimportada.posicoes_base, canonic_pos)
            np.testing.assert_allclose(reimportada.vertices[:, :3], dados[:, :3],
                                       rtol=0, atol=1e-5)
            np.testing.assert_allclose(reimportada.vertices[:, 6:8], dados[:, 6:8],
                                       rtol=0, atol=1e-6)

    def test_nao_exporta_valores_invalidos_nem_sobrescreve_destino(self):
        malha = self.malha
        dados = malha.vertices.copy()
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "modelo.obj"
            arquivo.write_text("sentinela", encoding="utf-8")
            dados[0, 0] = np.nan
            with self.assertRaisesRegex(ValueError, "não finitos"):
                exportar_obj(arquivo, malha, dados)
            self.assertEqual(arquivo.read_text(encoding="utf-8"), "sentinela")

            dados = malha.vertices.copy()
            with self.assertRaisesRegex(ValueError, "destino .obj"):
                exportar_obj(arquivo.with_suffix(".txt"), malha, dados)
            self.assertEqual(arquivo.read_text(encoding="utf-8"), "sentinela")

    def test_rejeita_posicoes_inconsistentes_na_costura(self):
        malha = self.malha
        dados = malha.vertices.copy()
        origem, contagem = np.unique(malha.origens, return_counts=True)
        compartilhado = origem[np.flatnonzero(contagem > 1)[0]]
        duplicados = np.flatnonzero(malha.origens == compartilhado)
        dados[duplicados[1], 0] += 0.5
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalido.obj"
            with self.assertRaisesRegex(ValueError, "Costura UV"):
                exportar_obj(arquivo, malha, dados)
            self.assertFalse(arquivo.exists())


if __name__ == "__main__":
    unittest.main()
