"""Buffers reutilizáveis do piloto Vulkan da interface original do MakeHuman.

O Object3D original permanece a fonte dos vértices e índices. Os buffers de
vértices e uniforms recebem dados novos a cada quadro (morphs, câmera,
materiais), mas não precisam ser recriados se o tamanho não mudou. Índices
são reenviados somente quando seu conteúdo muda, inclusive com mesmo tamanho.

WeakKeyDictionary evita manter objetos removidos de G.world vivos por causa
do cache. O cache não mantém referência forte ao Object3D.
"""

from weakref import WeakKeyDictionary

import numpy as np


class CacheBuffersVulkan:
    """Gerencia buffers por instância de lib.object3d.Object3D."""

    def __init__(self, device, wgpu):
        self.device = device
        self.wgpu = wgpu
        self._objetos = WeakKeyDictionary()

    def _sincronizar(self, estado, nome, dados, uso, enviar=True):
        """Recria apenas após mudança de tamanho; senão escreve no buffer."""
        tamanho = dados.nbytes
        if tamanho == 0 or tamanho % 4:
            raise ValueError("Buffer Vulkan deve ter tamanho positivo múltiplo de 4")
        buffer = estado.get(nome)
        if buffer is None or estado[nome + "_bytes"] != tamanho:
            buffer = self.device.create_buffer_with_data(
                data=dados,
                usage=uso | self.wgpu.BufferUsage.COPY_DST,
            )
            estado[nome] = buffer
            estado[nome + "_bytes"] = tamanho
        elif enviar:
            self.device.queue.write_buffer(buffer, 0, dados)
        return buffer

    def atualizar(self, obj, vertices, indices, uniforms):
        """Retorna (buffer_vértices, buffer_índices, buffer_uniforms).

        Vértices e uniforms sempre são sincronizados para refletir as
        mudanças feitas pelo próprio MakeHuman, mesmo quando arrays
        são modificados in-place. O snapshot dos índices também detecta
        alterações in-place do face mask sem depender de flags legadas.
        """
        vertices = np.ascontiguousarray(vertices, dtype=np.float32)
        indices = np.ascontiguousarray(indices, dtype=np.uint32)
        uniforms = np.ascontiguousarray(uniforms, dtype=np.float32)
        estado = self._objetos.get(obj)
        if estado is None:
            estado = {"indices_cpu": None}
            self._objetos[obj] = estado

        buf_v = self._sincronizar(
            estado, "vertices", vertices, self.wgpu.BufferUsage.VERTEX
        )
        # O índice do MakeHuman costuma ser estático entre morphs. A cópia
        # evita mascarar mudanças in-place em arrays compartilhados.
        mudou_indice = (
            estado["indices_cpu"] is None
            or not np.array_equal(estado["indices_cpu"], indices)
        )
        buf_i = self._sincronizar(
            estado, "indices", indices, self.wgpu.BufferUsage.INDEX,
            enviar=mudou_indice,
        )
        if mudou_indice:
            estado["indices_cpu"] = indices.copy()
        buf_u = self._sincronizar(
            estado, "uniforms", uniforms, self.wgpu.BufferUsage.UNIFORM
        )
        return buf_v, buf_i, buf_u
