"""Regressões do reuso de buffers da viewport Vulkan original.

Mocks verificam uploads e vida dos objetos, sem drivers ou PyOpenGL.
"""
import gc
from pathlib import Path
import sys
import unittest
import weakref

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "codigo" / "makehuman" / "lib"
sys.path.insert(0, str(ROOT))

from vulkan_buffers import CacheBuffersVulkan


class Usos:
    VERTEX = 1
    INDEX = 2
    UNIFORM = 4
    COPY_DST = 8


class WgpuFalso:
    BufferUsage = Usos


class BufferFalso:
    def __init__(self, dados, uso):
        self.dados = dados
        self.uso = uso


class FilaFalsa:
    def __init__(self):
        self.escritas = []

    def write_buffer(self, buffer, offset, dados):
        assert offset == 0
        valor = memoryview(np.ascontiguousarray(dados)).tobytes()
        buffer.dados = valor
        self.escritas.append((buffer, valor))


class DispositivoFalso:
    def __init__(self):
        self.criados = []
        self.queue = FilaFalsa()

    def create_buffer_with_data(self, *, data, usage):
        buffer = BufferFalso(memoryview(np.ascontiguousarray(data)).tobytes(), usage)
        self.criados.append(buffer)
        return buffer


class Objeto:
    pass


class CacheBuffersDaGuiOriginal(unittest.TestCase):
    def setUp(self):
        self.dispositivo = DispositivoFalso()
        self.cache = CacheBuffersVulkan(self.dispositivo, WgpuFalso)
        self.obj = Objeto()
        self.vertices = np.zeros((3, 12), np.float32)
        self.indices = np.array([0, 1, 2], np.uint32)
        self.uniforms = np.zeros(20, np.float32)

    def atualizar(self, *, passe="principal"):
        return self.cache.atualizar(
            self.obj, self.vertices, self.indices, self.uniforms, passe=passe,
        )

    def test_primeiro_frame_aloca_trio_e_copy_dst(self):
        trio = self.atualizar()
        self.assertEqual(len(self.dispositivo.criados), 3)
        self.assertEqual(len(self.dispositivo.queue.escritas), 0)
        self.assertTrue(all(buf.uso & Usos.COPY_DST for buf in trio))

    def test_frames_iguais_reutilizam_sem_upload_de_indices(self):
        antes = self.atualizar()
        depois = self.atualizar()
        self.assertTrue(all(a is b for a, b in zip(antes, depois)))
        self.assertEqual(len(self.dispositivo.criados), 3)
        self.assertEqual(
            [buffer for buffer, _ in self.dispositivo.queue.escritas],
            [antes[0], antes[2]],
        )

    def test_morph_e_camera_mudam_buffers_reutilizados(self):
        vb, ib, ub = self.atualizar()
        self.vertices[1, 2] = 0.375
        self.uniforms[-1] = 0.7
        self.assertEqual(self.atualizar(), (vb, ib, ub))
        self.assertAlmostEqual(
            float(np.frombuffer(vb.dados, dtype=np.float32)[14]), 0.375,
        )
        self.assertAlmostEqual(
            float(np.frombuffer(ub.dados, dtype=np.float32)[-1]), 0.7,
        )
        self.assertEqual(len(self.dispositivo.criados), 3)

    def test_indices_reordenados_mesmo_tamanho_sao_atualizados(self):
        _, ib, _ = self.atualizar()
        self.indices[:] = [2, 1, 0]
        self.assertIs(self.atualizar()[1], ib)
        np.testing.assert_array_equal(
            np.frombuffer(ib.dados, np.uint32), [2, 1, 0],
        )
        self.assertIn(ib, [buffer for buffer, _ in self.dispositivo.queue.escritas])

    def test_tamanho_diferente_recria_somente_buffer_afetado(self):
        vb, ib, ub = self.atualizar()
        self.indices = np.array([0, 1, 2, 2, 1, 0], np.uint32)
        depois = self.atualizar()
        self.assertIsNot(depois[1], ib)
        self.assertIs(depois[0], vb)
        self.assertIs(depois[2], ub)
        self.vertices = np.zeros((4, 12), np.float32)
        ultimos = self.atualizar()
        self.assertIsNot(ultimos[0], vb)
        self.assertIs(ultimos[1], depois[1])
        self.assertEqual(len(self.dispositivo.criados), 5)

    def test_passes_wireframe_nao_dividem_mesmo_buffer(self):
        principal = self.atualizar()
        wire = self.atualizar(passe="wireframe-linhas")
        preenchimento = self.atualizar(passe="wireframe-preenchimento")
        self.assertTrue(all(a is not b for a, b in zip(principal, wire)))
        self.assertTrue(all(a is not b for a, b in zip(principal, preenchimento)))
        self.assertEqual(len(self.dispositivo.criados), 9)
        self.assertEqual(self.atualizar(passe="wireframe-linhas"), wire)

    def test_remocao_do_object3d_libera_cache(self):
        self.atualizar()
        ref = weakref.ref(self.obj)
        del self.obj
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(len(self.cache._objetos), 0)

    def test_nao_retem_objeto_sem_weakref(self):
        from types import SimpleNamespace
        objeto = SimpleNamespace()
        for _ in range(2):
            self.cache.atualizar(
                objeto, self.vertices, self.indices, self.uniforms,
            )
        self.assertEqual(len(self.cache._objetos), 0)
        self.assertEqual(len(self.dispositivo.criados), 6)

    def test_rejeita_buffers_vazios_e_passe_invalido(self):
        with self.assertRaisesRegex(ValueError, "tamanho positivo"):
            self.cache.atualizar(
                self.obj, np.empty((0, 12), np.float32),
                self.indices, self.uniforms,
            )
        with self.assertRaisesRegex(ValueError, "passe"):
            self.atualizar(passe="")


if __name__ == "__main__":
    unittest.main()
