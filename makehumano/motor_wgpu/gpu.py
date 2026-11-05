"""Backend GPU experimental wgpu-py, independente do OpenGL legado.

Um MVP de triângulos indexados + depth buffer + textura RGBA + material WGSL.
Não oferece ainda seleção, animação nem os shaders avançados do MakeHuman.
"""

from pathlib import Path
import math

import numpy as np
import wgpu

from .malha import Malha
from .materiais import (Pele, textura_neutra, validar_rgba,
                        mapa_normal_neutro, mapa_rugosidade_neutro)


def perspectiva(fov, aspecto, perto=0.1, longe=200.0):
    f = 1.0 / math.tan(math.radians(fov) / 2)
    return np.array([
        [f / aspecto, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, longe / (perto - longe), perto * longe / (perto - longe)],
        [0, 0, -1, 0],
    ], dtype=np.float32)


def olhar_de(olho, alvo):
    olho = np.asarray(olho, dtype=np.float32)
    alvo = np.asarray(alvo, dtype=np.float32)
    f = alvo - olho
    f /= np.linalg.norm(f)
    direita = np.cross(f, [0, 1, 0])
    direita /= np.linalg.norm(direita)
    cima = np.cross(direita, f)
    rot = np.eye(4, dtype=np.float32)
    rot[0, :3] = direita
    rot[1, :3] = cima
    rot[2, :3] = -f
    move = np.eye(4, dtype=np.float32)
    move[:3, 3] = -olho
    return rot @ move


class MotorWgpu:
    def __init__(self, canvas, malha: Malha):
        self.canvas = canvas
        self.malha = malha
        self.pele = Pele()
        self.angulo = 0.0
        self.elevacao = 0.05
        self.distancia = 28.0
        self.frames = 0

        self.adapter = wgpu.gpu.request_adapter_sync(
            power_preference="high-performance", canvas=canvas
        )
        if self.adapter is None:
            raise RuntimeError("Nenhum adaptador wgpu compatível com a janela")
        self.device = self.adapter.request_device_sync()
        self.contexto = canvas.get_wgpu_context()
        self.formato = self.contexto.get_preferred_format(self.adapter)
        self.contexto.configure(device=self.device, format=self.formato)

        codigo = (Path(__file__).parent / "shaders" / "pele.wgsl").read_text(encoding="utf-8")
        shader = self.device.create_shader_module(code=codigo)
        self.pipeline = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader,
                entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=32,
                    step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(format="float32x3", offset=0, shader_location=0),
                        wgpu.VertexAttribute(format="float32x3", offset=12, shader_location=1),
                        wgpu.VertexAttribute(format="float32x2", offset=24, shader_location=2),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(topology="triangle-list", cull_mode="none"),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus",
                depth_write_enabled=True,
                depth_compare="less",
            ),
            multisample=wgpu.MultisampleState(),
            fragment=wgpu.FragmentState(
                module=shader,
                entry_point="fs_main",
                targets=[wgpu.ColorTargetState(format=self.formato)],
            ),
        )

        self.vertex_buffer = self.device.create_buffer_with_data(
            data=malha.vertices, usage=wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST
        )
        self.index_buffer = self.device.create_buffer_with_data(
            data=malha.indices, usage=wgpu.BufferUsage.INDEX
        )
        self.uniform_buffer = self.device.create_buffer(
            size=176, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST
        )
        self.sampler = self.device.create_sampler(
            mag_filter="linear", min_filter="linear",
            address_mode_u="repeat", address_mode_v="repeat",
        )
        self._depth_size = None
        self._depth_view = None
        self._texturas_gpu = {}
        self._bind_group = None
        self.normal_ativo = False
        self.rugosidade_ativa = False
        self._enviar_textura("cor", textura_neutra())
        self._enviar_textura("normal", mapa_normal_neutro())
        self._enviar_textura("rugosidade", mapa_rugosidade_neutro())
        self._criar_bind_group()
        self.canvas.request_draw(self.desenhar)

    def _enviar_textura(self, tipo: str, pixels):
        """Upload RGBA8 em textura filtrável; guarda os mesmos pixels na CPU."""
        pixels = validar_rgba(pixels)
        h, w = pixels.shape[:2]
        textura = self.device.create_texture(
            size=(w, h, 1),
            format="rgba8unorm",
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            dimension="2d",
            mip_level_count=1,
            sample_count=1,
        )
        self.device.queue.write_texture(
            wgpu.TexelCopyTextureInfo(texture=textura, mip_level=0, origin=(0, 0, 0)),
            pixels.tobytes(),
            wgpu.TexelCopyBufferLayout(offset=0, bytes_per_row=w * 4, rows_per_image=h),
            (w, h, 1),
        )
        self._texturas_gpu[tipo] = textura
        setattr(self, {
            "cor": "textura_cpu",
            "normal": "textura_normal_cpu",
            "rugosidade": "textura_rugosidade_cpu",
        }[tipo], pixels.copy())

    def _criar_bind_group(self):
        self._bind_group = self.device.create_bind_group(
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(
                    binding=0, resource=wgpu.BufferBinding(buffer=self.uniform_buffer)
                ),
                wgpu.BindGroupEntry(
                    binding=1, resource=self._texturas_gpu["cor"].create_view()
                ),
                wgpu.BindGroupEntry(binding=2, resource=self.sampler),
                wgpu.BindGroupEntry(
                    binding=3, resource=self._texturas_gpu["normal"].create_view()
                ),
                wgpu.BindGroupEntry(
                    binding=4, resource=self._texturas_gpu["rugosidade"].create_view()
                ),
            ],
        )

    def atualizar_textura(self, pixels, *, solicitar_redesenho=True):
        """Substitui a textura base de pele em tempo real."""
        self._enviar_textura("cor", pixels)
        self._criar_bind_group()
        if solicitar_redesenho:
            self.canvas.request_draw()

    def atualizar_mapa_normal(self, pixels=None):
        """RGB tangente OpenGL (+Y); None restaura a normal geométrica."""
        ativo = pixels is not None
        self._enviar_textura(
            "normal", pixels if ativo else mapa_normal_neutro()
        )
        self.normal_ativo = ativo
        self._criar_bind_group()
        self.canvas.request_draw()

    def atualizar_mapa_rugosidade(self, pixels=None):
        """Canal R multiplica rugosidade base; None restaura valor do slider."""
        ativo = pixels is not None
        self._enviar_textura(
            "rugosidade", pixels if ativo else mapa_rugosidade_neutro()
        )
        self.rugosidade_ativa = ativo
        self._criar_bind_group()
        self.canvas.request_draw()

    def atualizar_vertices(self, vertices: np.ndarray):
        """Transfere a geometria deformada para o vertex buffer já existente.

        Os índices, as UVs e o pipeline Vulkan permanecem os mesmos.
        """
        vertices = np.asarray(vertices, dtype=np.float32)
        if vertices.shape != self.malha.vertices.shape:
            raise ValueError(
                f"Malha deformada precisa ter formato {self.malha.vertices.shape}, "
                f"recebido {vertices.shape}"
            )
        if not np.isfinite(vertices).all():
            raise ValueError("A geometria contém NaN ou infinito")
        self.device.queue.write_buffer(
            self.vertex_buffer, 0, np.ascontiguousarray(vertices)
        )
        self.canvas.request_draw()

    def ajustar_pele(self, *, cor=None, rugosidade=None, dispersao=None):
        self.pele.atualizar(cor=cor, rugosidade=rugosidade,
                            dispersao=dispersao)
        self.canvas.request_draw()

    def ajustar_camera(self, *, angulo=None, elevacao=None, distancia=None):
        if angulo is not None:
            self.angulo = float(angulo)
        if elevacao is not None:
            self.elevacao = float(elevacao)
        if distancia is not None:
            self.distancia = max(10.0, float(distancia))
        self.canvas.request_draw()

    def _tamanho_tela(self):
        largura, altura = self.canvas.get_physical_size()
        return max(1, int(largura)), max(1, int(altura))

    def _atualizar_uniformes(self, largura, altura):
        centro = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        olho = centro + self.distancia * np.array([
            math.sin(self.angulo) * math.cos(self.elevacao),
            math.sin(self.elevacao),
            math.cos(self.angulo) * math.cos(self.elevacao),
        ], dtype=np.float32)
        model = np.eye(4, dtype=np.float32)
        mvp = perspectiva(48.0, largura / altura) @ olhar_de(olho, centro) @ model
        # WGSL mat4x4 é column-major; a transposição preserva o produto.
        payload = b"".join([
            mvp.T.copy().tobytes(),
            model.T.copy().tobytes(),
            np.array([*self.pele.cor, 1.0], dtype=np.float32).tobytes(),
            np.array([self.pele.rugosidade, float(self.normal_ativo),
                      self.pele.dispersao, 0], dtype=np.float32).tobytes(),
            np.array([*olho, 1.0], dtype=np.float32).tobytes(),
        ])
        self.device.queue.write_buffer(self.uniform_buffer, 0, payload)

    def desenhar(self):
        largura, altura = self._tamanho_tela()
        if self._depth_size != (largura, altura):
            depth = self.device.create_texture(
                size=(largura, altura, 1),
                format="depth24plus",
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
                dimension="2d",
            )
            self._depth_view = depth.create_view()
            self._depth_size = (largura, altura)
        self._atualizar_uniformes(largura, altura)
        quadro = self.contexto.get_current_texture().create_view()
        encoder = self.device.create_command_encoder()
        passagem = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=quadro, load_op=wgpu.LoadOp.clear,
                store_op=wgpu.StoreOp.store,
                clear_value=(0.08, 0.105, 0.14, 1.0),
            )],
            depth_stencil_attachment=wgpu.RenderPassDepthStencilAttachment(
                view=self._depth_view,
                depth_clear_value=1.0,
                depth_load_op=wgpu.LoadOp.clear,
                depth_store_op=wgpu.StoreOp.store,
            ),
        )
        passagem.set_pipeline(self.pipeline)
        passagem.set_bind_group(0, self._bind_group)
        passagem.set_vertex_buffer(0, self.vertex_buffer)
        passagem.set_index_buffer(self.index_buffer, "uint32")
        passagem.draw_indexed(int(self.malha.indices.size))
        passagem.end()
        self.device.queue.submit([encoder.finish()])
        self.frames += 1
