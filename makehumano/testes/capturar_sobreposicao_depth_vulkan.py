"""Teste GPU Vulkan com duas superfícies sobrepostas, depth e A2C MSAA4×.

O fragment shader emite vermelho na frente, azul no fundo. O segundo draw
ocorre atrás geometricamente, mas pode sobrescrever o primeiro caso a
escrita Z esteja desativada. Tudo é temporário e fora do renderer real.
"""
from pathlib import Path
import numpy as np

from contrato_sobreposicao_depth_sintetica import (
    CASOS_SOBREPOSICAO, criar_registro, sequencia_draw,
    vertices_com_profundidade,
)


def _shader_face(face, a2c):
    vertices = vertices_com_profundidade(face)
    pontos = ",\n        ".join(
        "vec3<f32>({:.9f}, {:.9f}, {:.9f})".format(x, y, z)
        for x, y, z in vertices
    )
    cor = (
        "vec4<f32>(1.0, 0.0, 0.0, {:.9f})".format(
            128 / 255.0 if a2c else 1.0
        )
        if face == "frente" else
        "vec4<f32>(0.0, 0.0, 1.0, 1.0)"
    )
    return """
@vertex fn vs_main(@builtin(vertex_index) vid: u32) -> @builtin(position) vec4<f32> {{
    let pos = array<vec3<f32>, 3>(
        {}
    );
    return vec4<f32>(pos[vid], 1.0);
}}
@fragment fn fs_main() -> @location(0) vec4<f32> {{
    return {};
}}
""".format(pontos, cor)


def capturar_sobreposicao_vulkan(cena, destino_json):
    wgpu, dev = cena.wgpu, cena.device
    destino_json = Path(destino_json)
    controles = {}
    for nome, a2c, escreve_z, ordem in CASOS_SOBREPOSICAO:
        pipelines = {}
        for passo in sequencia_draw(a2c, escreve_z, ordem):
            face = passo["face"]
            shader = dev.create_shader_module(
                code=_shader_face(face, passo["a2c"])
            )
            pipelines[face] = dev.create_render_pipeline(
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
                    )]
                ),
                depth_stencil=wgpu.DepthStencilState(
                    format="depth24plus",
                    depth_write_enabled=passo["escrita_z"],
                    depth_compare="less",
                ),
                multisample=wgpu.MultisampleState(
                    count=4, alpha_to_coverage_enabled=passo["a2c"]
                ),
            )
        cor = cena.framebuffer_offscreen(64, 64, formato="rgba8unorm")
        multisample = dev.create_texture(
            size=(64, 64, 1), format="rgba8unorm", sample_count=4,
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
        )
        depth = dev.create_texture(
            size=(64, 64, 1), format="depth24plus", sample_count=4,
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
        )
        encoder = dev.create_command_encoder()
        passagem = encoder.begin_render_pass(
            color_attachments=[wgpu.RenderPassColorAttachment(
                view=multisample.create_view(), resolve_target=cor.create_view(),
                load_op="clear", store_op="store",
                clear_value=(0.0, 0.0, 0.0, 0.0),
            )],
            depth_stencil_attachment=wgpu.RenderPassDepthStencilAttachment(
                view=depth.create_view(), depth_load_op="clear",
                depth_store_op="store", depth_clear_value=1.0,
            ),
        )
        sequencia = sequencia_draw(a2c, escreve_z, ordem)
        for passo in sequencia:
            passagem.set_pipeline(pipelines[passo["face"]])
            passagem.draw(3)
        passagem.end()
        dev.queue.submit([encoder.finish()])
        rgba = np.ascontiguousarray(cena.ler_framebuffer_rgba(cor))
        if rgba.shape != (64, 64, 4) or rgba.dtype != np.uint8:
            raise RuntimeError("Framebuffer sintético Vulkan depth RGB8 inválido")
        rgb = np.ascontiguousarray(rgba[:, :, :3])
        arquivo = destino_json.with_name(
            destino_json.stem + "-sobreposicao-" + nome + ".png"
        )
        controles[nome] = {
            **criar_registro(
                rgb, arquivo, nome=nome, a2c=a2c,
                escrita_z=escreve_z, ordem=ordem, rastros=sequencia,
            ),
            "formato_depth_pipeline": "depth24plus",
            "amostras_depth_configuradas": 4,
            "nota_rastros": (
                "Estados extraídos da configuração temporária dos "
                "pipelines criados; não há readback do estado WGPU."
            ),
        }
    return {
        "backend": "Vulkan",
        "tipo": "SOBREPOSICAO_DEPTH_A2C_SINTETICA",
        "controles": controles,
        "nao_homologado": True,
    }
