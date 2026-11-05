"""Testes da exportação OBJ/MTL/PNG sem dependência de Qt ou de GPU."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_wgpu.exportar import exportar_obj_com_material
from motor_wgpu.malha import carregar_obj, caminho_base_obj
from motor_wgpu.materiais import Pele, textura_neutra
from motor_wgpu.materiais_obj import (
    ASSINATURA_PNG, caminhos_materiais, escrever_png_rgba,
    texto_mtl, validar_material,
)
from motor_wgpu.morphs import Deformador, ler_target, pasta_targets


def decodificar_png_simples(arquivo: Path):
    """Decodifica PNG RGBA8 com filtro 0, verificando chunks/CRC (sem Pillow)."""
    dados = arquivo.read_bytes()
    assert dados.startswith(ASSINATURA_PNG)
    offset = len(ASSINATURA_PNG)
    dimensoes = None
    zdata = bytearray()
    while offset < len(dados):
        tamanho = struct.unpack_from(">I", dados, offset)[0]
        offset += 4
        tipo = dados[offset:offset + 4]
        offset += 4
        payload = dados[offset:offset + tamanho]
        offset += tamanho
        crc = struct.unpack_from(">I", dados, offset)[0]
        offset += 4
        assert zlib.crc32(tipo + payload) & 0xFFFFFFFF == crc
        if tipo == b"IHDR":
            w, h, bits, cor, comp, filt, interc = struct.unpack(
                ">IIBBBBB", payload
            )
            assert (bits, cor, comp, filt, interc) == (8, 6, 0, 0, 0)
            dimensoes = w, h
        elif tipo == b"IDAT":
            zdata.extend(payload)
        elif tipo == b"IEND":
            break
    assert dimensoes is not None
    w, h = dimensoes
    descomprimido = zlib.decompress(zdata)
    linhas = [
        descomprimido[k * (w * 4 + 1):(k + 1) * (w * 4 + 1)]
        for k in range(h)
    ]
    assert all(linha[0] == 0 for linha in linhas)
    return np.frombuffer(
        b"".join(linha[1:] for linha in linhas), dtype=np.uint8
    ).reshape(h, w, 4)


class TestarExportacaoMateriais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.malha = carregar_obj(caminho_base_obj())

    def test_png_preserva_rgba_e_orientacao(self):
        pixels = np.array([
            [[255, 12, 34, 255], [0, 220, 0, 128]],
            [[3, 6, 9, 24], [11, 22, 33, 44]],
        ], dtype=np.uint8)
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "textura.png"
            escrever_png_rgba(imagem, pixels)
            np.testing.assert_array_equal(decodificar_png_simples(imagem), pixels)

    def test_obj_mtl_png_preserva_material_uv_e_forma_deformada(self):
        m = self.malha
        deformador = Deformador(m)
        alvo = ler_target(
            pasta_targets() / "nose/nose-scale-horiz-incr.target",
            len(m.posicoes_base),
        )
        deformado = deformador.definir_peso("nariz", alvo, 0.55).copy()
        pele = Pele(cor=(0.74, 0.51, 0.35), rugosidade=0.34)
        pixels = np.array([
            [[140, 80, 70, 255], [160, 100, 90, 128]],
            [[190, 110, 65, 255], [200, 120, 80, 255]],
        ], dtype=np.uint8)
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "personagem.obj"
            obj, mtl, png = exportar_obj_com_material(
                destino, m, deformado, pele, pixels
            )
            self.assertEqual(obj, destino)
            self.assertEqual((mtl.name, png.name),
                             ("personagem_pele.mtl", "personagem_pele.png"))
            texto_obj = obj.read_text(encoding="utf-8")
            texto_mtl_gerado = mtl.read_text(encoding="utf-8")
            self.assertIn(f"mtllib {mtl.name}\n", texto_obj)
            self.assertIn("usemtl PeleMakeHumano\n", texto_obj)
            self.assertIn(f"map_Kd {png.name}\n", texto_mtl_gerado)
            self.assertIn("Kd 0.740000 0.510000 0.350000", texto_mtl_gerado)
            self.assertIn("illum 2", texto_mtl_gerado)
            np.testing.assert_array_equal(decodificar_png_simples(png), pixels)

            reimportado = carregar_obj(obj)
            np.testing.assert_array_equal(reimportado.origens, m.origens)
            np.testing.assert_array_equal(reimportado.indices, m.indices)
            np.testing.assert_allclose(
                reimportado.vertices[:, :3], deformado[:, :3], rtol=0, atol=1e-5
            )
            np.testing.assert_allclose(
                reimportado.vertices[:, 6:8], deformado[:, 6:8], rtol=0, atol=1e-6
            )

    def test_sem_textura_externa_exporta_neutra_e_tom_do_material(self):
        with tempfile.TemporaryDirectory() as pasta:
            obj, mtl, png = exportar_obj_com_material(
                Path(pasta) / "pele.obj", self.malha,
                self.malha.vertices, Pele(cor=(0.3, 0.4, 0.5))
            )
            np.testing.assert_array_equal(decodificar_png_simples(png), textura_neutra())
            self.assertIn("Kd 0.300000 0.400000 0.500000",
                          mtl.read_text(encoding="utf-8"))
            self.assertTrue(obj.exists())

    def test_validacao_ocorre_antes_de_alterar_arquivos(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "pele.obj"
            mtl, png = caminhos_materiais(destino)
            for arquivo in (destino, mtl, png):
                arquivo.write_bytes(b"arquivo-antigo")
            with self.assertRaisesRegex(ValueError, "RGBA"):
                exportar_obj_com_material(
                    destino, self.malha, self.malha.vertices,
                    Pele(), np.zeros((2, 2, 3), dtype=np.uint8)
                )
            for arquivo in (destino, mtl, png):
                self.assertEqual(arquivo.read_bytes(), b"arquivo-antigo")

    def test_nome_sanitizado_e_intervalos(self):
        with tempfile.TemporaryDirectory() as pasta:
            mtl, png = caminhos_materiais(Path(pasta) / "João personagem.obj")
            self.assertTrue(mtl.name.endswith("_pele.mtl"))
            self.assertTrue(png.name.endswith("_pele.png"))
            self.assertNotIn(" ", mtl.name)
        with self.assertRaises(ValueError):
            texto_mtl(Pele(), "subpasta/textura.png")
        with self.assertRaises(ValueError):
            validar_material(Pele(), np.zeros((1, 1, 3), np.uint8))


if __name__ == "__main__":
    unittest.main()
