"""Cache dos buffers WebGPU da viewport Vulkan do MakeHuman original.

A geometria e os uniforms continuam sendo produzidos a cada desenho pelo
MakeHuman; somente as alocações GPU são reaproveitadas quando cabem no buffer.
Chaves de objeto são fracas para não prolongar a vida de malhas removidas.
Separar os passes de wireframe evita sobrescrever buffers em um render pass.
"""

from weakref import WeakKeyDictionary

import numpy as np


class CacheBuffersVulkan:
    """Reutiliza VERTEX, INDEX e UNIFORM por objeto e tipo de passe."""

    def __init__(self, device, wgpu):
        self.device = device
        self.wgpu = wgpu
        self._objetos = WeakKeyDictionary()

    def _sincronizar(self, estado, nome, dados, uso, *, enviar=True):
        tamanho = dados.nbytes
        if tamanho < 4 or tamanho % 4:
            raise ValueError("Buffer Vulkan deve ter tamanho positivo múltiplo de 4")
        buffer = estado.get(nome)
        if buffer is None or estado[nome + "_bytes"] != tamanho:
            buffer = self.device.create_buffer_with_data(
                data=dados, usage=uso | self.wgpu.BufferUsage.COPY_DST,
            )
            estado[nome] = buffer
            estado[nome + "_bytes"] = tamanho
        elif enviar:
            self.device.queue.write_buffer(buffer, 0, dados)
        return buffer

    def atualizar(self, obj, vertices, indices, uniforms, *, passe="principal"):
        """Retorna (vértices, índices, uniforms) após sincronizar dados atuais.

        Vertices e uniforms são reenviados inclusive após mutações in-place.
        Índices são reenviados somente se a topologia ou máscara mudar, mesmo
        quando a quantidade de elementos continuar igual.
        """
        vertices = np.ascontiguousarray(vertices, dtype=np.float32)
        indices = np.ascontiguousarray(indices, dtype=np.uint32)
        uniforms = np.ascontiguousarray(uniforms, dtype=np.float32)
        if not isinstance(passe, str) or not passe:
            raise ValueError("Identificador de passe Vulkan inválido")

        try:
            # Algumas malhas de teste são SimpleNamespace sem suporte a
            # weakref/hash: elas funcionam sem cache, jamais retidas.
            estados = self._objetos.get(obj)
            if estados is None:
                estados = {}
                self._objetos[obj] = estados
            estado = estados.setdefault(passe, {"indices_cpu": None})
        except TypeError:
            estado = {"indices_cpu": None}

        buf_v = self._sincronizar(
            estado, "vertices", vertices, self.wgpu.BufferUsage.VERTEX,
        )
        anterior = estado["indices_cpu"]
        alterados = (anterior is None or not np.array_equal(anterior, indices))
        buf_i = self._sincronizar(
            estado, "indices", indices, self.wgpu.BufferUsage.INDEX,
            enviar=alterados,
        )
        if alterados:
            estado["indices_cpu"] = indices.copy()
        buf_u = self._sincronizar(
            estado, "uniforms", uniforms, self.wgpu.BufferUsage.UNIFORM,
        )
        return buf_v, buf_i, buf_u
