"""Probe GPU A2C Vulkan with one fullscreen triangle, constant linear color.

Only tests; no Phong, textures, lighting, depth, blend, or scene geometry.
One 64x64 RGBA8 color target is resolved from a real 4x MSAA attachment.
"""
import hashlib
from pathlib import Path

import numpy as np

from auditar_cobertura_a2c_sintetica import (
    CASOS, geometria_do_caso, registrar_rgb, salvar_png_rgb, vertices_do_caso,
)


def shader_vertices(nome):
    # Os números são definidos UMA vez no contrato GL/Vulkan, nunca
    # ajustados por backend para forçar correspondência.
    pontos = ",
        ".join(
        "vec2<f32>({:.9f}, {:.9f})".format(x, y)
        for x, y in vertices_do_caso(nome)
    )
    return """
@vertex fn vs_main(@builtin(vertex_index) vid: u32) -> @builtin(position) vec4<f32> {{
    let corners = array<vec2<f32>, 3>(
        {}
    );
    return vec4<f32>(corners[vid], 0.0, 1.0);
}}
""".format(pontos)


def capturar_sintetico_vulkan(cena, destino_json):
    wgpu, dev = cena.wgpu, cena.device
    destino_json = Path(destino_json)
    controles = {}

    for nome, amostras, a2c, alfa in CASOS:
        shader = dev.create_shader_module(
            code=shader_vertices(nome) + """
@fragment fn fs_main() -> @location(0) vec4<f32> {
    return vec4<f32>(1.0, 1.0, 1.0, """ +
            format(alfa / 255, ".9f") + """);
}
"""
        )
        pipeline = dev.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=shader, entry_point="vs_main", buffers=[],
            ),
            primitive=wgpu.PrimitiveState(
                topology="triangle-list", cull_mode="none",
            ),
            fragment=wgpu.FragmentState(
                module=shader, entry_point="fs_main",
                targets=[wgpu.ColorTargetState(
                    format="rgba8unorm", blend=None,
                )],
            ),
            multisample=wgpu.MultisampleState(
                count=amostras, alpha_to_coverage_enabled=a2c,
            ),
        )
        target = cena.framebuffer_offscreen(64, 64, formato="rgba8unorm")
        if amostras == 4:
            multi = dev.create_texture(
                size=(64, 64, 1), format="rgba8unorm", sample_count=4,
                usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            )
            render_view = multi.create_view()
            resolve_view = target.create_view()
        else:
            render_view = target.create_view()
            resolve_view = None
        encoder = dev.create_command_encoder()
        passage = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=render_view, resolve_target=resolve_view,
                load_op="clear", store_op="store",
                clear_value=(0.0, 0.0, 0.0, 0.0),
            )],
        )
        passage.set_pipeline(pipeline)
        passage.draw(3)
        passage.end()
        dev.queue.submit([encoder.finish()])
        rgba = np.ascontiguousarray(cena.ler_framebuffer_rgba(target))
        if rgba.shape != (64, 64, 4) or rgba.dtype != np.uint8:
            raise RuntimeError("Framebuffer sintético Vulkan RGBA8 inesperado")
        rgb = np.ascontiguousarray(rgba[:, :, :3])
        png = destino_json.with_name(destino_json.stem + "-sintetico-" + nome + ".png")
        hash_png = salvar_png_rgb(rgb, png)
        controles[nome] = {
            **registrar_rgb(rgb),
            "alfa_u8": alfa,
            "geometria": geometria_do_caso(nome),
            "amostras": amostras,
            "a2c_ativo": a2c,
            "blend_ativo": False,
            "profundidade_ativa": False,
            "png": str(png),
            "sha256_png": hash_png,
        }
    return {
        "backend": "Vulkan",
        "tipo": "A2C_SINTETICO_UMA_SUPERFICIE",
        "saida": "rgba8unorm linear 64x64, RGB de branco com fundo preto",
        "controles": controles,
        "nao_homologado": True,
    }
