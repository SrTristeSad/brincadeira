"""Auditoria isolada RGBA: arquivo/CPU/upload/amostragem GPU sem overdraw.

Cria uma superfície de cobertura total gerada por vertex_index. A textura é
o mesmo recurso de CenaVulkan._textura usado pelo corpo; sampler linear
cena.amostra. A2C e BLEND estão permanentemente desligados no pipeline
diagnóstico. RGB na saída não depende de alpha no shader.

Não testa o shader Phong nem aprova paridade visual; é somente controle
de carregamento de RGBA, textura e resolve MSAA, sem alterar produção.
"""
import hashlib
import numpy as np

from diagnosticar_a2c_msaa import comparar_rgb
from textura_alpha_controle import dados_textura_alfa_parcial


SHADER_DE_PROVA = """
struct VSOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
};
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var sampler_tex: sampler;

@vertex fn vs_main(@builtin(vertex_index) vid: u32) -> VSOut {
    let pontos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>(3.0, -1.0),
        vec2<f32>(-1.0, 3.0)
    );
    let pos = pontos[vid];
    var out: VSOut;
    out.pos = vec4<f32>(pos, 0.0, 1.0);
    out.uv = (pos + vec2<f32>(1.0, 1.0)) * 0.5;
    return out;
}
@fragment fn fs_main(input: VSOut) -> @location(0) vec4<f32> {
    let pixel = textureSample(tex, sampler_tex, input.uv);
    // NÃO multiplicar RGB por alpha; output premult seria outro teste.
    return vec4<f32>(pixel.rgb, pixel.a);
}
"""


def dados_cpu_alpha(caminhos):
    """Audita o loader real, sem converter RGB do PNG via Pillow."""
    from vulkan_texture import getTexture
    resultado = {}
    rgb_base = None
    for alpha, caminho in sorted(caminhos.items()):
        valor = int(alpha)
        if valor not in (64, 128, 192):
            raise ValueError("Alfa inesperado na prova RGBA")
        tex = getTexture(str(caminho))
        if tex is None:
            raise RuntimeError("Textura de controle não carregada: " + str(caminho))
        rgba = np.ascontiguousarray(np.asarray(tex.data))
        esperado = dados_textura_alfa_parcial(alfa=valor)
        if (rgba.shape != (32, 32, 4) or rgba.dtype != np.uint8
                or not np.array_equal(rgba, esperado)):
            raise RuntimeError("Loader CPU RGBA divergiu do PNG determinístico")
        if rgb_base is not None and not np.array_equal(rgba[:, :, :3], rgb_base):
            raise RuntimeError("RGB do loader depende indevidamente do alfa")
        rgb_base = rgba[:, :, :3].copy()
        resultado[str(valor)] = {
            "sha256_rgba": hashlib.sha256(rgba.tobytes()).hexdigest(),
            "sha256_rgb": hashlib.sha256(
                np.ascontiguousarray(rgba[:, :, :3]).tobytes()
            ).hexdigest(),
            "alfa_min": int(rgba[:, :, 3].min()),
            "alfa_max": int(rgba[:, :, 3].max()),
        }
    if set(resultado) != {"64", "128", "192"}:
        raise RuntimeError("CPU sem os três níveis RGBA")
    return resultado


def renderizar_amostra_sintetica(cena, recurso, pipeline, *, amostras):
    """Lê o mesmo recurso de textura em um triângulo full-screen único."""
    wgpu = cena.wgpu
    largura, altura = 64, 64
    alvo = cena.framebuffer_offscreen(largura, altura, formato="rgba8unorm")
    view_alvo = alvo.create_view()
    if amostras == 4:
        view_msaa = cena.device.create_texture(
            size=(largura, altura, 1), format="rgba8unorm",
            sample_count=4, usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
        ).create_view()
        target = view_alvo
        render_view = view_msaa
    elif amostras == 1:
        target = None
        render_view = view_alvo
    else:
        raise ValueError("Prova GPU usa 1 ou 4 amostras")
    grupo = cena.device.create_bind_group(
        layout=pipeline.get_bind_group_layout(0),
        entries=[
            wgpu.BindGroupEntry(binding=0, resource=recurso.create_view()),
            wgpu.BindGroupEntry(binding=1, resource=cena.amostra),
        ],
    )
    encoder = cena.device.create_command_encoder()
    passagem = encoder.begin_render_pass(
        color_attachments=[
            wgpu.RenderPassColorAttachment(
                view=render_view, resolve_target=target, load_op="clear",
                store_op="store", clear_value=(0.0, 0.0, 0.0, 0.0),
            ),
        ]
    )
    passagem.set_pipeline(pipeline)
    passagem.set_bind_group(0, grupo)
    passagem.draw(3)
    passagem.end()
    cena.device.queue.submit([encoder.finish()])
    return np.ascontiguousarray(cena.ler_framebuffer_rgba(alvo))


def verificar_textura_na_gpu(cena, caminhos):
    """Compara RGB pós-amostragem da GPU em 1× e 4×, sem cena 3D."""
    cpu = dados_cpu_alpha(caminhos)
    wgpu = cena.wgpu
    modulo = cena.device.create_shader_module(code=SHADER_DE_PROVA)
    amostragens = {}
    for amostras in (1, 4):
        pipeline = cena.device.create_render_pipeline(
            layout=wgpu.AutoLayoutMode.auto,
            vertex=wgpu.VertexState(
                module=modulo, entry_point="vs_main", buffers=[],
            ),
            primitive=wgpu.PrimitiveState(
                topology="triangle-list", cull_mode="none",
            ),
            fragment=wgpu.FragmentState(
                module=modulo, entry_point="fs_main",
                targets=[
                    wgpu.ColorTargetState(format="rgba8unorm", blend=None),
                ],
            ),
            multisample=wgpu.MultisampleState(
                count=amostras, alpha_to_coverage_enabled=False,
            ),
        )
        capturas = {}
        for alpha, caminho in sorted(caminhos.items()):
            recurso = cena._textura(str(caminho))
            pixels = renderizar_amostra_sintetica(
                cena, recurso, pipeline, amostras=amostras,
            )
            capturas[int(alpha)] = pixels
        base = capturas[128]
        controles = {}
        for alpha in (64, 128, 192):
            r = capturas[alpha]
            a = comparar_rgb(base[:, :, :3], r[:, :, :3], tolerancia=0)
            controles[str(alpha)] = {
                "sha256_rgb": hashlib.sha256(
                    np.ascontiguousarray(r[:, :, :3]).tobytes()
                ).hexdigest(),
                "sha256_rgba": hashlib.sha256(r.tobytes()).hexdigest(),
                "pixels_rgb_diferentes_de_a128": a["pixels_divergentes"],
                "erro_max_rgb_a128": a["erro_maximo_rgb"],
                "alfa_min": int(r[:, :, 3].min()),
                "alfa_max": int(r[:, :, 3].max()),
            }
        amostragens[str(amostras)] = {
            "amostras": amostras,
            "pipeline_blend_habilitado": False,
            "pipeline_a2c_habilitado": False,
            "uma_superficie_sem_sobreposicao": True,
            "dimensoes": [64, 64],
            "controles": controles,
            "rgb_igual_em_todos_os_alfas": all(
                x["pixels_rgb_diferentes_de_a128"] == 0
                for x in controles.values()
            ),
        }
    return {
        "tipo": "AUDITORIA_RGBA_CPU_GPU_TRIANGULO_SEM_SOBREPOSICAO",
        "nao_homologado": True,
        "cpu": cpu,
        "gpu": amostragens,
        "limites": (
            "Usa o loader e textura do Vulkan real, mas shader de teste "
            "sem Phong, sombra ou geometria de personagem; não prova qual "
            "estado do renderer é responsável por divergências do corpo."
        ),
    }
