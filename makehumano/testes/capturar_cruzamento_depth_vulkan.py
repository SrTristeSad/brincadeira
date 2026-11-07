"""Probe Vulkan de duas faces que se cruzam em profundidade, MSAA4×/A2C.

Pipelines de teste independentes do shader Phong e do renderer de
produção. O estado é o solicitado na construção WGPU, sem readback
dos registradores de GPU.
"""
from pathlib import Path
import numpy as np

from contrato_cruzamento_depth_sintetica import (
    CASOS_CRUZAMENTO, passos, registrar, vertices,
)


def shader_face(face, a2c):
    pontos_face = vertices(face)
    pontos = ",\n        ".join(
        "vec3<f32>({:.9f}, {:.9f}, {:.9f})".format(x, y, z)
        for x, y, z in pontos_face
    )
    cor = (
        "vec4<f32>(1.0, 0.0, 0.0, {:.9f})".format(
            128 / 255.0 if a2c else 1.0
        )
        if face == "vermelho" else "vec4<f32>(0.0, 0.0, 1.0, 1.0)"
    )
    return """
@vertex fn vs_main(@builtin(vertex_index) vid: u32) -> @builtin(position) vec4<f32> {{
    let pontos = array<vec3<f32>, 3>(
        {}
    );
    return vec4<f32>(pontos[vid], 1.0);
}}
@fragment fn fs_main() -> @location(0) vec4<f32> {{
    return {};
}}
""".format(pontos, cor)


def capturar_cruzamento_depth_vulkan(cena, destino_json):
    wgpu, device = cena.wgpu, cena.device
    destino_json = Path(destino_json)
    controles = {}
    for caso in CASOS_CRUZAMENTO:
        nome, a2c, escrita_z, ordem = caso
        draw_passos = passos(a2c, escrita_z, ordem)
        pipelines = {}
        for passo in draw_passos:
            face = passo["face"]
            shader = device.create_shader_module(code=shader_face(face, passo["a2c"]))
            pipelines[face] = device.create_render_pipeline(
                layout=wgpu.AutoLayoutMode.auto,
                vertex=wgpu.VertexState(
                    module=shader, entry_point="vs_main", buffers=[]
                ),
                primitive=wgpu.PrimitiveState(
                    topology="triangle-list", cull_mode="none"
                ),
                fragment=wgpu.FragmentState(
                    module=shader, entry_point="fs_main",
                    targets=[wgpu.ColorTargetState(
                        format="rgba8unorm", blend=None
                    )],
                ),
                depth_stencil=wgpu.DepthStencilState(
                    format="depth24plus",
                    depth_write_enabled=passo["escrita_z"],
                    depth_compare=passo["depth_compare"],
                ),
                multisample=wgpu.MultisampleState(
                    count=4, alpha_to_coverage_enabled=passo["a2c"]
                ),
            )
        resolved = cena.framebuffer_offscreen(64, 64, formato="rgba8unorm")
        multi = device.create_texture(
            size=(64, 64, 1), format="rgba8unorm",
            sample_count=4, usage=wgpu.TextureUsage.RENDER_ATTACHMENT
        )
        depth = device.create_texture(
            size=(64, 64, 1), format="depth24plus",
            sample_count=4, usage=wgpu.TextureUsage.RENDER_ATTACHMENT
        )
        encoder = device.create_command_encoder()
        passagem = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=multi.create_view(), resolve_target=resolved.create_view(),
                load_op="clear", store_op="store",
                clear_value=(0.0, 0.0, 0.0, 0.0),
            )],
            depth_stencil_attachment=wgpu.RenderPassDepthStencilAttachment(
                view=depth.create_view(), depth_load_op="clear",
                depth_store_op="store", depth_clear_value=1.0
            ),
        )
        for passo in draw_passos:
            passagem.set_pipeline(pipelines[passo["face"]])
            passagem.draw(3)
        passagem.end()
        device.queue.submit([encoder.finish()])
        rgba = np.ascontiguousarray(cena.ler_framebuffer_rgba(resolved))
        if rgba.dtype != np.uint8 or rgba.shape != (64, 64, 4):
            raise RuntimeError("Readback coplanar Vulkan não retornou RGBA8 64²")
        rgb = np.ascontiguousarray(rgba[:, :, :3])
        png = destino_json.with_name(
            destino_json.stem + "-cruzamento-" + nome + ".png"
        )
        controles[nome] = {
            **registrar(rgb, png, caso, draw_passos),
            "formato_depth_pipeline": "depth24plus",
            "amostras_depth_configuradas": 4,
            "nota_estados": (
                "Rastros do pipeline WGPU solicitado; sem readback do estado da GPU"
            ),
        }
    return {
        "tipo": "CRUZAMENTO_DEPTH_MSAA4X",
        "backend": "Vulkan",
        "controles": controles,
        "nao_homologado": True,
    }
