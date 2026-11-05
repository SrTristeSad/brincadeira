"""Primeira ponte Vulkan com a CENA ORIGINAL do MakeHuman (G.world).

Não carrega um segundo personagem, não aplica alvos morfológicos próprios.
Converte o Object3D de renderização que o MakeHuman já atualiza em dados
para GPU. O piloto é incompleto: picking, transparência, render offscreen
e shaders customizados ainda precisam ser migrados antes de remover OpenGL.
"""

import os

import numpy as np


def assinatura_textura(caminho):
    """Identifica mudanças de arquivo sem depender de OpenGL ou Qt."""
    if not caminho:
        return None
    try:
        info = os.stat(caminho)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)



def preparar_malha_original(obj):
    """Retorna vértices float32 [n,12] e triângulos uint32 de Object3D.

    O objeto aqui é lib/object3d.Object3D (já desenhado por glmodule), não
    um novo parser de base.obj. Respeita os índices UV desenrolados e as
    máscaras de faces atualizados pelo próprio module3d.Object3D.
    """
    posicoes = np.asarray(obj.verts, dtype=np.float32)
    if posicoes.ndim != 2 or posicoes.shape[1] != 3:
        raise ValueError("Object3D original: posições inválidas")
    n = len(posicoes)
    normais = np.asarray(obj.norms, dtype=np.float32)
    if normais.shape != posicoes.shape:
        raise ValueError("Object3D original: normais inválidas")
    if obj.hasUVs:
        uvs = np.asarray(obj.UVs, dtype=np.float32)
        if uvs.shape != (n, 2):
            raise ValueError("Object3D original: coordenadas UV inválidas")
    else:
        uvs = np.zeros((n, 2), dtype=np.float32)

    cores = np.asarray(obj.color, dtype=np.uint8)
    if cores.shape != (n, 4):
        raise ValueError("Object3D original: cores RGBA inválidas")
    vertices = np.empty((n, 12), dtype=np.float32)
    vertices[:, :3] = posicoes
    vertices[:, 3:6] = normais
    vertices[:, 6:8] = uvs
    vertices[:, 8:12] = cores.astype(np.float32) / 255.0

    face = np.asarray(obj.primitives)
    # O MakeHuman cria também overlays auxiliares sem faces; eles podem
    # chegar com array vazio unidimensional. Não são erros de geometria.
    if face.size == 0:
        return (
            np.ascontiguousarray(vertices),
            np.empty(0, dtype=np.uint32),
        )
    if face.ndim != 2 or face.shape[1] not in (2, 3, 4):
        raise ValueError(
            "Object3D original: primitiva não triangular não suportada "
            + str(face.shape)
        )
    if np.any(face < 0) or np.any(face >= n):
        raise ValueError("Object3D original: índice de face fora da malha")
    face = np.asarray(face, dtype=np.uint32)
    if face.shape[1] == 4:
        # MakeHuman mantém triangulações na sequência das faces visíveis.
        indices = np.concatenate(
            (face[:, [0, 1, 2]], face[:, [0, 2, 3]]), axis=0
        )
    else:
        indices = face
    if face.shape[1] == 2:
        # O grid e outras linhas auxiliares têm pares de vértices.
        indices = indices[indices[:, 0] != indices[:, 1]]
    else:
        # Quads degenerados são usados pelo MakeHuman para representar tris.
        indices = indices[
            (indices[:, 0] != indices[:, 1])
            & (indices[:, 1] != indices[:, 2])
            & (indices[:, 0] != indices[:, 2])
        ]
    if not np.isfinite(vertices).all():
        raise ValueError("Object3D original: coordenadas não finitas")
    return (np.ascontiguousarray(vertices),
            np.ascontiguousarray(indices.reshape(-1), dtype=np.uint32))


def matriz_wgpu(camera, obj):
    """Reaproveita câmera/modelo originais e converte depth GL [-1,1] a [0,1]."""
    if not camera.updated:
        camera.updateCamera()
        camera.updated = True
    proj, view = camera.getMatrices(0)
    model = camera.getModelMatrix(obj)
    proj = np.asarray(proj, dtype=np.float32)
    view = np.asarray(view, dtype=np.float32)
    model = np.asarray(model, dtype=np.float32)
    if any(m.shape != (4, 4) or not np.isfinite(m).all()
           for m in (proj, view, model)):
        raise ValueError("Matrizes da câmera original inválidas")
    conversao_z = np.eye(4, dtype=np.float32)
    conversao_z[2, 2] = 0.5
    conversao_z[2, 3] = 0.5
    return np.ascontiguousarray(conversao_z @ proj @ view @ model)


class CenaVulkan:
    """Renderização piloto de objetos G.world na própria janela MakeHuman."""

    def __init__(self, canvas):
        import wgpu
        from PyQt5 import QtGui

        self.wgpu = wgpu
        self.QtGui = QtGui
        self.canvas = canvas
        self.adapter = wgpu.gpu.request_adapter_sync(
            power_preference="high-performance", canvas=canvas
        )
        if self.adapter is None:
            raise RuntimeError("Nenhum adaptador Vulkan disponível")
        # Sem fallback OpenGL: o piloto só opera com Vulkan.
        if "vulkan" not in str(self.adapter.info).lower():
            raise RuntimeError(
                "Backend não é Vulkan: " + str(self.adapter.info)
            )
        self.device = self.adapter.request_device_sync()
        self.contexto = canvas.get_wgpu_context()
        self.formato = self.contexto.get_preferred_format(self.adapter)
        self.contexto.configure(device=self.device, format=self.formato)
        codigo = """
struct Globals { mvp: mat4x4<f32>, cor: vec4<f32> };
@group(0) @binding(0) var<uniform> dados: Globals;
@group(0) @binding(1) var mapa: texture_2d<f32>;
@group(0) @binding(2) var amostra: sampler;
struct Entrada {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv: vec2<f32>,
    @location(3) cor: vec4<f32>,
};
struct Fragmento {
    @builtin(position) pos: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) cor: vec4<f32>,
};
@vertex fn vs_main(v: Entrada) -> Fragmento {
    var o: Fragmento;
    o.pos = dados.mvp * vec4<f32>(v.pos, 1.0);
    o.normal = v.normal;
    o.uv = v.uv;
    o.cor = v.cor;
    return o;
}
@fragment fn fs_main(i: Fragmento) -> @location(0) vec4<f32> {
    let tex = textureSample(mapa, amostra, vec2<f32>(i.uv.x, 1.0-i.uv.y));
    let luz = 0.30 + 0.70 * max(
        dot(normalize(i.normal), normalize(vec3<f32>(0.4, 0.8, 0.5))), 0.0
    );
    return vec4<f32>(tex.rgb * i.cor.rgb * dados.cor.rgb * luz,
                     tex.a * i.cor.a * dados.cor.a);
}
"""
        shader = self.device.create_shader_module(code=codigo)
        self.pipeline = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader, entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=48, step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(
                            format="float32x3", offset=0, shader_location=0
                        ),
                        wgpu.VertexAttribute(
                            format="float32x3", offset=12, shader_location=1
                        ),
                        wgpu.VertexAttribute(
                            format="float32x2", offset=24, shader_location=2
                        ),
                        wgpu.VertexAttribute(
                            format="float32x4", offset=32, shader_location=3
                        ),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(
                topology="triangle-list", cull_mode="none"
            ),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus", depth_write_enabled=True,
                depth_compare="less-equal"
            ),
            fragment=wgpu.FragmentState(
                module=shader, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(format=self.formato)],
            ),
        )
        # A grade de referência original (back_grid) usa GL_LINES.
        # Mantê-la com seus mesmos índices, cores e transformações.
        self.pipeline_linhas = self.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader, entry_point="vs_main",
                buffers=[wgpu.VertexBufferLayout(
                    array_stride=48, step_mode="vertex",
                    attributes=[
                        wgpu.VertexAttribute(
                            format="float32x3", offset=0, shader_location=0
                        ),
                        wgpu.VertexAttribute(
                            format="float32x3", offset=12, shader_location=1
                        ),
                        wgpu.VertexAttribute(
                            format="float32x2", offset=24, shader_location=2
                        ),
                        wgpu.VertexAttribute(
                            format="float32x4", offset=32, shader_location=3
                        ),
                    ],
                )],
            ),
            primitive=wgpu.PrimitiveState(
                topology="line-list", cull_mode="none"
            ),
            depth_stencil=wgpu.DepthStencilState(
                format="depth24plus", depth_write_enabled=False,
                depth_compare="less-equal"
            ),
            fragment=wgpu.FragmentState(
                module=shader, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(format=self.formato)],
            ),
        )
        self.amostra = self.device.create_sampler(
            mag_filter="linear", min_filter="linear"
        )
        self._texturas = {}
        self._depth = None
        self._depth_size = None
        self.frames = 0
        self.objetos_desenhados = 0
        self.linhas_desenhadas = 0
        self._primitivas_pendentes = set()

    def invalidar_texturas(self, caminho=None):
        """Invalida texturas da cena; a próxima renderização recarrega na GPU."""
        if caminho is None:
            self._texturas.clear()
        else:
            self._texturas.pop(str(caminho), None)

    def _textura(self, caminho):
        chave = str(caminho or "")
        assinatura = assinatura_textura(chave)
        entrada = self._texturas.get(chave)
        if entrada is not None and entrada[0] == assinatura:
            return entrada[1]
        if chave:
            imagem = self.QtGui.QImage(chave)
        else:
            imagem = self.QtGui.QImage()
        if imagem.isNull():
            pixels = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
        else:
            imagem = imagem.convertToFormat(
                self.QtGui.QImage.Format_RGBA8888
            )
            w, h = imagem.width(), imagem.height()
            pixels = np.frombuffer(
                imagem.bits().asstring(w*h*4), dtype=np.uint8
            ).reshape((h, w, 4)).copy()
        h, w = pixels.shape[:2]
        wgpu = self.wgpu
        textura = self.device.create_texture(
            size=(w, h, 1), dimension="2d", format="rgba8unorm",
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.device.queue.write_texture(
            wgpu.TexelCopyTextureInfo(
                texture=textura, mip_level=0, origin=(0, 0, 0)
            ),
            pixels.tobytes(),
            wgpu.TexelCopyBufferLayout(
                offset=0, bytes_per_row=w*4, rows_per_image=h
            ),
            (w, h, 1),
        )
        self._texturas[chave] = (assinatura, textura)
        return textura

    def desenhar(self, mundo, cameras, *, cor_fundo=(0.2, 0.2, 0.2, 1)):
        wgpu = self.wgpu
        tamanho = tuple(self.canvas.get_physical_size())
        if len(tamanho) < 2 or tamanho[0] < 1 or tamanho[1] < 1:
            return
        tamanho = (int(tamanho[0]), int(tamanho[1]))
        if self._depth_size != tamanho:
            depth = self.device.create_texture(
                size=(tamanho[0], tamanho[1], 1),
                format="depth24plus",
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            )
            self._depth = depth.create_view()
            self._depth_size = tamanho

        encoder = self.device.create_command_encoder()
        passagem = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=self.contexto.get_current_texture().create_view(),
                resolve_target=None,
                load_op="clear",
                store_op="store",
                clear_value=tuple(cor_fundo),
            )],
            depth_stencil_attachment=wgpu.RenderPassDepthStencilAttachment(
                view=self._depth,
                depth_load_op="clear", depth_store_op="store",
                depth_clear_value=1.0,
            ),
        )
        passagem.set_pipeline(self.pipeline)
        self.objetos_desenhados = 0
        self.linhas_desenhadas = 0
        if mundo is not None:
            for obj in sorted(mundo, key=lambda item: item.priority):
                if not obj.visibility:
                    continue
                try:
                    vertices, indices = preparar_malha_original(obj)
                except ValueError as erro:
                    if "primitiva não triangular" not in str(erro):
                        raise
                    # Ainda não há pipeline de linhas/points do overlay Qt.
                    # A migração será considerada parcial até esse caso
                    # receber tratamento explícito; não lançar exceção em loop.
                    if obj.name not in self._primitivas_pendentes:
                        self._primitivas_pendentes.add(obj.name)
                        print(
                            "MAKEHUMANO_VULKAN: pendente primitiva auxiliar "
                            + str(obj.name) + ": " + str(erro),
                            flush=True,
                        )
                    continue
                if not len(vertices) or not len(indices):
                    continue
                primitiva = np.asarray(obj.primitives)
                linhas = primitiva.ndim == 2 and primitiva.shape[1] == 2
                pipeline = self.pipeline_linhas if linhas else self.pipeline
                passagem.set_pipeline(pipeline)
                cam = cameras[obj.cameraMode]
                mvp = matriz_wgpu(cam, obj)
                material = getattr(obj, "material", None)
                diffuse = getattr(
                    getattr(material, "diffuseColor", None), "values",
                    (1.0, 1.0, 1.0)
                )
                cor = np.array(
                    [*np.asarray(diffuse, dtype=np.float32)[:3], 1.0],
                    dtype=np.float32,
                )
                uniforms = np.concatenate(
                    (mvp.T.reshape(-1), cor)
                ).astype(np.float32)
                buf_u = self.device.create_buffer_with_data(
                    data=uniforms, usage=wgpu.BufferUsage.UNIFORM
                )
                buf_v = self.device.create_buffer_with_data(
                    data=vertices, usage=wgpu.BufferUsage.VERTEX
                )
                buf_i = self.device.create_buffer_with_data(
                    data=indices, usage=wgpu.BufferUsage.INDEX
                )
                textura = self._textura(getattr(obj, "texture", None))
                bind = self.device.create_bind_group(
                    layout=pipeline.get_bind_group_layout(0),
                    entries=[
                        wgpu.BindGroupEntry(
                            binding=0,
                            resource=wgpu.BufferBinding(buffer=buf_u),
                        ),
                        wgpu.BindGroupEntry(
                            binding=1, resource=textura.create_view()
                        ),
                        wgpu.BindGroupEntry(
                            binding=2, resource=self.amostra
                        ),
                    ],
                )
                passagem.set_bind_group(0, bind)
                passagem.set_vertex_buffer(0, buf_v)
                passagem.set_index_buffer(buf_i, "uint32")
                passagem.draw_indexed(len(indices))
                self.objetos_desenhados += 1
                if linhas:
                    self.linhas_desenhadas += len(indices) // 2
        passagem.end()
        self.device.queue.submit([encoder.finish()])
        self.frames += 1
