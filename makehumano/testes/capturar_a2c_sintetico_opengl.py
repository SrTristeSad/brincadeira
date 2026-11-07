"""Probe GL A2C in original compatibility context with a standalone MSAA FBO.

Uses GLSL 120 fixed-color fullscreen triangle, real 4-sample renderbuffer,
glBlitFramebuffer resolve, no app geometry/light/texture/depth/blending.
Restores GL state and deletes every temporary GPU object.
"""
from pathlib import Path

import numpy as np

from auditar_cobertura_a2c_sintetica import CASOS, registrar_rgb, salvar_png_rgb


VS = """
#version 120
void main() {
    gl_Position = gl_Vertex;
}
"""
FS = """
#version 120
uniform float uAlpha;
void main() {
    gl_FragColor = vec4(1.0, 1.0, 1.0, uAlpha);
}
"""


def compilar(GL, tipo, codigo):
    shader = GL.glCreateShader(tipo)
    GL.glShaderSource(shader, codigo)
    GL.glCompileShader(shader)
    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        error = GL.glGetShaderInfoLog(shader)
        GL.glDeleteShader(shader)
        raise RuntimeError("GLSL sintético não compilou: " + str(error))
    return shader


def criar_framebuffer(GL, amostras):
    fbo = GL.glGenFramebuffers(1)
    rb = GL.glGenRenderbuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb)
    if amostras == 4:
        GL.glRenderbufferStorageMultisample(
            GL.GL_RENDERBUFFER, 4, GL.GL_RGBA8, 64, 64
        )
    else:
        GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_RGBA8, 64, 64)
    GL.glFramebufferRenderbuffer(
        GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_RENDERBUFFER, rb
    )
    GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
    if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("FBO diagnóstico GL incompleto")
    return fbo, rb


def capturar_sintetico_opengl(destino_json):
    from OpenGL import GL

    destino_json = Path(destino_json)
    # In this GL 2.1 compatibility context both read/draw bindings matter.
    old_program = int(GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM))
    old_read = int(GL.glGetIntegerv(GL.GL_READ_FRAMEBUFFER_BINDING))
    old_draw = int(GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING))
    old_renderbuffer = int(GL.glGetIntegerv(GL.GL_RENDERBUFFER_BINDING))
    old_viewport = [int(x) for x in GL.glGetIntegerv(GL.GL_VIEWPORT)]
    old_clear = [float(x) for x in GL.glGetFloatv(GL.GL_COLOR_CLEAR_VALUE)]
    old_pack = int(GL.glGetIntegerv(GL.GL_PACK_ALIGNMENT))
    old_mask = [bool(x) for x in GL.glGetBooleanv(GL.GL_COLOR_WRITEMASK)]
    estados = (
        GL.GL_BLEND, GL.GL_DEPTH_TEST, GL.GL_STENCIL_TEST,
        GL.GL_DITHER, GL.GL_SCISSOR_TEST, GL.GL_SAMPLE_ALPHA_TO_COVERAGE,
        GL.GL_MULTISAMPLE,
    )
    old_enabled = {cap: bool(GL.glIsEnabled(cap)) for cap in estados}
    shader_v = shader_f = program = None
    buffers = []
    controles = {}
    try:
        for cap in estados:
            GL.glDisable(cap)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glColorMask(True, True, True, True)
        GL.glViewport(0, 0, 64, 64)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
        shader_v = compilar(GL, GL.GL_VERTEX_SHADER, VS)
        shader_f = compilar(GL, GL.GL_FRAGMENT_SHADER, FS)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, shader_v)
        GL.glAttachShader(program, shader_f)
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError("GLSL sintético não linkou: " + str(
                GL.glGetProgramInfoLog(program)
            ))
        GL.glUseProgram(program)
        uniform_alpha = GL.glGetUniformLocation(program, "uAlpha")
        if uniform_alpha < 0:
            raise RuntimeError("Uniform uAlpha não está ativo")
        for nome, amostras, a2c, alfa in CASOS:
            fbo, rb = criar_framebuffer(GL, amostras)
            buffers.append(("framebuffer", fbo))
            buffers.append(("renderbuffer", rb))
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
            amostras_observadas = int(GL.glGetIntegerv(GL.GL_SAMPLES))
            if amostras_observadas != (4 if amostras == 4 else 0):
                raise RuntimeError("GL_SAMPLES inesperado no FBO sintético")
            if a2c:
                GL.glEnable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
            else:
                GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
            GL.glClearColor(0, 0, 0, 0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glUniform1f(uniform_alpha, alfa / 255.0)
            GL.glBegin(GL.GL_TRIANGLES)
            GL.glVertex2f(-1.0, -1.0)
            GL.glVertex2f(3.0, -1.0)
            GL.glVertex2f(-1.0, 3.0)
            GL.glEnd()
            if amostras == 4:
                resolve, res_rb = criar_framebuffer(GL, 1)
                buffers.append(("framebuffer", resolve))
                buffers.append(("renderbuffer", res_rb))
                GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, fbo)
                GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, resolve)
                GL.glBlitFramebuffer(
                    0, 0, 64, 64, 0, 0, 64, 64,
                    GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST,
                )
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, resolve)
            rgba = np.frombuffer(
                bytes(GL.glReadPixels(0, 0, 64, 64, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)),
                dtype=np.uint8,
            ).reshape((64, 64, 4))
            rgb = np.ascontiguousarray(np.flipud(rgba[:, :, :3]))
            png = destino_json.with_name(
                destino_json.stem + "-sintetico-" + nome + ".png"
            )
            sha_png = salvar_png_rgb(rgb, png)
            controles[nome] = {
                **registrar_rgb(rgb),
                "alfa_u8": alfa,
                "amostras": amostras,
                "amostras_fbo_observadas": amostras_observadas,
                "a2c_ativo": a2c,
                "blend_ativo": False,
                "profundidade_ativa": False,
                "png": str(png),
                "sha256_png": sha_png,
            }
        return {
            "backend": "OpenGL",
            "tipo": "A2C_SINTETICO_UMA_SUPERFICIE",
            "saida": "rgba8unorm linear 64x64, RGB de branco com fundo preto",
            "controles": controles,
            "nao_homologado": True,
        }
    finally:
        GL.glUseProgram(old_program)
        if program:
            GL.glDeleteProgram(program)
        if shader_v:
            GL.glDeleteShader(shader_v)
        if shader_f:
            GL.glDeleteShader(shader_f)
        for tipo, objeto in reversed(buffers):
            if tipo == "framebuffer":
                GL.glDeleteFramebuffers(1, [objeto])
            else:
                GL.glDeleteRenderbuffers(1, [objeto])
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, old_read)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, old_draw)
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, old_renderbuffer)
        GL.glViewport(*old_viewport)
        GL.glClearColor(*old_clear)
        GL.glColorMask(*old_mask)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, old_pack)
        for cap, habilitado in old_enabled.items():
            (GL.glEnable if habilitado else GL.glDisable)(cap)
