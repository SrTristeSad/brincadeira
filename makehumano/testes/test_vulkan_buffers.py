"""Regressões do cache GPU usado pela viewport original do MakeHuman.

Mocks exercitam a interface de alocação/upload do wgpu sem exigir Vulkan
nem PyOpenGL no processo de testes.
"""

import gc
from pathlib import Path
import sys
import unittest
import weakref

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "codigo" / "makehuman" / "lib"))

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


class TestarCacheBuffersDaGuiOriginal(unittest.TestCase):
    def setUp(self):
        self.dispositivo = DispositivoFalso()
        self.cache = CacheBuffersVulkan(self.dispositivo, WgpuFalso)
        self.obj = Objeto()
        self.vertices = np.zeros((3, 12), dtype=np.float32)
        self.indices = np.array([0, 1, 2], dtype=np.uint32)
        self.uniforms = np.zeros(20, dtype=np.float32)

    def atualizar(self):
        return self.cache.atualizar(
            self.obj, self.vertices, self.indices, self.uniforms
        )

    def test_primeiro_quadro_cria_tres_buffers_com_copy_dst(self):
        vertices, indices, uniforms = self.atualizar()
        self.assertEqual(len(self.dispositivo.criados), 3)
        self.assertEqual(len(self.dispositivo.queue.escritas), 0)
        self.assertTrue(vertices.uso & Usos.COPY_DST)
        self.assertTrue(indices.uso & Usos.COPY_DST)
        self.assertTrue(uniforms.uso & Usos.COPY_DST)

    def test_quadro_igual_reutiliza_buffers_sem_reenviar_indices(self):
        antes = self.atualizar()
        depois = self.atualizar()
        self.assertTrue(all(a is b for a, b in zip(antes, depois)))
        self.assertEqual(len(self.dispositivo.criados), 3)
        self.assertEqual(
            [buf for buf, _ in self.dispositivo.queue.escritas],
            [antes[0], antes[2]],
        )

    def test_morph_in_place_atualiza_vertices_sem_recriar(self):
        vb, ib, ub = self.atualizar()
        self.vertices[1, 2] = 0.375
        depois = self.atualizar()
        self.assertIs(depois[0], vb)
        self.assertIs(depois[1], ib)
        self.assertIs(depois[2], ub)
        self.assertEqual(len(self.dispositivo.criados), 3)
        self.assertEqual(np.frombuffer(vb.dados, dtype=np.float32)[14], 0.375)

    def test_face_mask_mesmo_tamanho_reenvia_indices_mutaveis(self):
        _, ib, _ = self.atualizar()
        self.indices[:] = [2, 1, 0]
        depois = self.atualizar()
        self.assertIs(depois[1], ib)
        self.assertEqual(len(self.dispositivo.criados), 3)
        np.testing.assert_array_equal(
            np.frombuffer(ib.dados, dtype=np.uint32), [2, 1, 0]
        )
        self.assertIn(ib, [buf for buf, _ in self.dispositivo.queue.escritas])

    def test_mudanca_de_topologia_ou_numero_vertices_realoca_apenas_necessario(self):
        vb, ib, ub = self.atualizar()
        self.indices = np.array([0, 1, 2, 2, 1, 0], dtype=np.uint32)
        atual = self.atualizar()
        self.assertIsNot(atual[1], ib)
        self.assertIs(atual[0], vb)
        self.assertIs(atual[2], ub)
        self.assertEqual(len(self.dispositivo.criados), 4)
        self.vertices = np.zeros((4, 12), dtype=np.float32)
        novo = self.atualizar()
        self.assertIsNot(novo[0], vb)
        self.assertIs(novo[1], atual[1])
        self.assertEqual(len(self.dispositivo.criados), 5)

    def test_camera_material_alterados_atualizam_uniforms(self):
        _, _, ub = self.atualizar()
        self.uniforms[-1] = 0.7
        self.atualizar()
        self.assertAlmostEqual(
            float(np.frombuffer(ub.dados, dtype=np.float32)[-1]), 0.7
        )
        self.assertEqual(len(self.dispositivo.criados), 3)

    def test_objetos_diferentes_nao_compartilham_buffers(self):
        primeiro = self.atualizar()
        segundo = self.cache.atualizar(
            Objeto(), self.vertices, self.indices, self.uniforms
        )
        self.assertTrue(all(a is not b for a, b in zip(primeiro, segundo)))
        self.assertEqual(len(self.dispositivo.criados), 6)

    def test_cache_nao_conserva_objetos_removidos(self):
        self.atualizar()
        referencia = weakref.ref(self.obj)
        del self.obj
        gc.collect()
        self.assertIsNone(referencia())
        self.assertEqual(len(self.cache._objetos), 0)


if __name__ == "__main__":
    unittest.main()
