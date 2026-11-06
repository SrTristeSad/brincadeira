"""Rasterização de skins UV sobre framebuffer Vulkan, sem glmodule.

Reaproveita os arrays de vértices, índices, UVs e cores do MakeHuman.
Suporta triângulos, quads e linhas; texturas Image/Texture são imagens CPU.
"""

import numpy as np

from vulkan_scene import pixels_textura_rgba


def preparar_skin(verts_per_primitive, verts, index=None, UVs=None, color=None):
    """Retorna vértices [posição xyz, textura xyzw, cor rgba] e índices."""
    pos = np.asarray(verts, dtype=np.float32)
    if pos.ndim != 2 or pos.shape[1] not in (2, 3):
        raise ValueError("Skin Vulkan exige vértices Nx2 ou Nx3")
    if not np.isfinite(pos).all():
        raise ValueError("Vértices UV não finitos")
    n = len(pos)
    if verts_per_primitive not in (2, 3, 4):
        raise NotImplementedError("Skin Vulkan aceita GL_LINES, TRIANGLES e QUADS")
    if index is None:
        if n % verts_per_primitive:
            raise ValueError("Número de vértices incompatível com a primitiva")
        faces = np.arange(n, dtype=np.uint32).reshape(-1, verts_per_primitive)
    else:
        faces = np.asarray(index)
        if faces.ndim != 2 or faces.shape[1] != verts_per_primitive:
            raise ValueError("Índices da skin não correspondem à primitiva")
        if np.any(faces < 0) or np.any(faces >= n):
            raise ValueError("Índices UV fora da malha")
        faces = np.asarray(faces, dtype=np.uint32)
    if verts_per_primitive == 4:
        ids = np.concatenate((faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]))
    else:
        ids = faces
    if verts_per_primitive == 2:
        ids = ids[ids[:, 0] != ids[:, 1]]
    else:
        ids = ids[
            (ids[:, 0] != ids[:, 1]) & (ids[:, 1] != ids[:, 2])
            & (ids[:, 0] != ids[:, 2])
        ]
    uv = np.zeros((n, 2), np.float32) if UVs is None else np.asarray(UVs, np.float32)
    if uv.ndim != 2 or uv.shape[0] != n or uv.shape[1] not in (2, 3, 4) or not np.isfinite(uv).all():
        raise ValueError("UVs de skin inválidas")
    if color is None:
        col = np.ones((n, 4), np.float32)
    else:
        col = np.asarray(color, np.uint8)
        if col.shape != (n, 4):
            raise ValueError("Cores da skin devem ter 4 canais")
        col = col.astype(np.float32) / 255.0
    vertices = np.zeros((n, 11), dtype=np.float32)
    vertices[:, :pos.shape[1]] = pos
    vertices[:, 6] = 1.0
    vertices[:, 3:3 + uv.shape[1]] = uv
    vertices[:, 7:11] = col
    return (
        np.ascontiguousarray(vertices),
        np.ascontiguousarray(ids.ravel(), dtype=np.uint32),
        verts_per_primitive == 2,
    )


def normalizar_cor_fundo(cor):
    """Recebe RGBA 0..1 ou 0..255 e devolve cor WebGPU."""
    if cor is None:
        return (0.0, 0.0, 0.0, 0.0)
    valores = np.asarray(cor, dtype=np.float32)
    if valores.shape != (4,) or not np.isfinite(valores).all():
        raise ValueError("Cor de fundo inválida")
    if valores.max() > 1:
        valores /= 255.0
    return tuple(float(v) for v in np.clip(valores, 0, 1))


def _matriz4(valor):
    if valor is None:
        return np.eye(4, dtype=np.float32)
    matriz = np.asarray(valor, dtype=np.float32)
    if matriz.shape != (4, 4) or not np.isfinite(matriz).all():
        raise ValueError("Matriz de skin inválida")
    return matriz


def _pipeline_skin(cena, linhas):
    """Cria pipeline GPU para o renderizador UV do MakeHuman."""
    cache = getattr(cena, "_pipelines_skin", None)
    if cache is None:
        cache = cena._pipelines_skin = {}
    if linhas in cache:
        return cache[linhas]
    wgpu = cena.wgpu
    wgsl = """
struct Uniforms {
    modelo: mat4x4<f32>,
    textura: mat4x4<f32>,
    opcoes: vec4<f32>,
};
@group(0) @binding(0) var<uniform> uni: Uniforms;
@group(0) @binding(1) var tex: texture_2d<f32>;
@group(0) @binding(2) var filtragem: sampler;

struct Entrada {
    @location(0) pos: vec3<f32>,
    @location(1) uv: vec4<f32>,
    @location(2) cor: vec4<f32>,
};
struct Saida {
    @builtin(position) clip: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) cor: vec4<f32>,
};
@vertex fn vs_skin(i: Entrada) -> Saida {
    var o: Saida;
    let p = uni.modelo * vec4<f32>(i.pos, 1.0);
    o.clip = vec4<f32>(2.0*p.x-p.w, 2.0*p.y-p.w, 0.5*p.w, p.w);
    let uv4 = uni.textura * i.uv;
    o.uv = uv4.xy / uv4.w;
    o.cor = i.cor;
    return o;
}
@fragment fn fs_skin(i: Saida) -> @location(0) vec4<f32> {
    let sampled = textureSample(tex, filtragem, vec2<f32>(i.uv.x, 1.0 - i.uv.y));
    let cor = select(vec4<f32>(1.0), sampled, uni.opcoes.x > 0.5);
    return cor * i.cor;
}
"""
    shader = cena.device.create_shader_module(code=wgsl)
    blend = wgpu.BlendState(
        color=wgpu.BlendComponent(
            src_factor="src-alpha", dst_factor="one-minus-src-alpha",
        ),
        alpha=wgpu.BlendComponent(
            src_factor="one", dst_factor="one-minus-src-alpha",
        ),
    )
    pipeline = cena.device.create_render_pipeline(
        layout=wgpu.AutoLayoutMode.auto,
        vertex=wgpu.VertexState(
            module=shader, entry_point="vs_skin",
            buffers=[wgpu.VertexBufferLayout(
                array_stride=44, step_mode="vertex",
                attributes=[
                    wgpu.VertexAttribute(
                        format="float32x3", offset=0, shader_location=0,
                    ),
                    wgpu.VertexAttribute(
                        format="float32x4", offset=12, shader_location=1,
                    ),
                    wgpu.VertexAttribute(
                        format="float32x4", offset=28, shader_location=2,
                    ),
                ],
            )],
        ),
        primitive=wgpu.PrimitiveState(
            topology="line-list" if linhas else "triangle-list",
            cull_mode="none",
        ),
        fragment=wgpu.FragmentState(
            module=shader, entry_point="fs_skin",
            targets=[wgpu.ColorTargetState(format=cena.formato, blend=blend)],
        ),
    )
    cache[linhas] = pipeline
    return pipeline


def render_skin(cena, dst, vertsPerPrimitive, verts, index=None,
                objectMatrix=None, texture=None, UVs=None,
                textureMatrix=None, color=None, clearColor=None):
    """Implementa o contrato mh.renderSkin em um render pass de Vulkan."""
    from image import Image
    from vulkan_texture import Texture
    wgpu = cena.wgpu
    if isinstance(dst, tuple):
        largura, altura = dst
        origem = None
    elif hasattr(dst, "width") and hasattr(dst, "height"):
        largura, altura = dst.width, dst.height
        origem = getattr(dst, "data", None)
    else:
        raise ValueError("Destino de skin inválido")
    largura, altura = int(largura), int(altura)
    geometria, indices, linhas = preparar_skin(
        vertsPerPrimitive, verts, index, UVs, color,
    )
    textura_alvo = cena.framebuffer_offscreen(largura, altura)
    limpa = True
    if clearColor is None and origem is not None:
        rgba = pixels_textura_rgba(origem)
        if rgba.shape[:2] != (altura, largura):
            raise ValueError("Tamanho dos pixels de destino incompatível")
        if cena.formato.startswith("bgra"):
            rgba = np.ascontiguousarray(rgba[:, :, [2, 1, 0, 3]])
        cena.device.queue.write_texture(
            wgpu.TexelCopyTextureInfo(
                texture=textura_alvo, mip_level=0, origin=(0, 0, 0),
            ),
            rgba.tobytes(),
            wgpu.TexelCopyBufferLayout(
                offset=0, bytes_per_row=largura * 4, rows_per_image=altura,
            ),
            (largura, altura, 1),
        )
        limpa = False
    pipeline = _pipeline_skin(cena, linhas)
    encoder = cena.device.create_command_encoder()
    passada = encoder.begin_render_pass(
        color_attachments=[wgpu.RenderPassColorAttachment(
            view=textura_alvo.create_view(),
            resolve_target=None,
            load_op="clear" if limpa else "load",
            store_op="store",
            clear_value=normalizar_cor_fundo(clearColor),
        )],
    )
    if len(indices):
        modelo = _matriz4(objectMatrix)
        texmat = _matriz4(textureMatrix)
        opcoes = np.array([float(texture is not None and UVs is not None),
                           0, 0, 0], dtype=np.float32)
        uniforms = np.concatenate(
            (modelo.T.ravel(), texmat.T.ravel(), opcoes),
        ).astype(np.float32)
        bu = cena.device.create_buffer_with_data(
            data=uniforms, usage=wgpu.BufferUsage.UNIFORM,
        )
        bv = cena.device.create_buffer_with_data(
            data=geometria, usage=wgpu.BufferUsage.VERTEX,
        )
        bi = cena.device.create_buffer_with_data(
            data=indices, usage=wgpu.BufferUsage.INDEX,
        )
        tex = cena._textura(texture)
        grupo = cena.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                wgpu.BindGroupEntry(binding=0, resource=wgpu.BufferBinding(buffer=bu)),
                wgpu.BindGroupEntry(binding=1, resource=tex.create_view()),
                wgpu.BindGroupEntry(binding=2, resource=cena.amostra),
            ],
        )
        passada.set_pipeline(pipeline)
        passada.set_bind_group(0, grupo)
        passada.set_vertex_buffer(0, bv)
        passada.set_index_buffer(bi, "uint32")
        passada.draw_indexed(len(indices))
    passada.end()
    cena.device.queue.submit([encoder.finish()])
    resultado = cena.ler_framebuffer_rgb(textura_alvo)
    if isinstance(dst, Texture):
        # Preserva conteúdo atualizado de Texture CPU para passes seguintes.
        canais = dst.data.shape[2]
        canais_render = cena.ler_framebuffer_rgba(textura_alvo)
        dst._data = np.ascontiguousarray(Image(data=canais_render).convert(canais).data)
        import time
        dst.modified = time.time_ns()
        cena.invalidar_texturas()
    return Image(data=resultado)
