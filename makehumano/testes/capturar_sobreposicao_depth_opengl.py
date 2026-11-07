"""Teste GPU OpenGL independente: duas faces, depth 4× e A2C.

GLSL120, FBO color+depth multisample real, resolve via blit. Sem material,
textura, Phong, iluminação ou blending. Todos os estados/resources temporários
são restaurados ou liberados ao terminar.
"""
from pathlib import Path
import numpy as np

from contrato_sobreposicao_depth_sintetica import (
    CASOS_SOBREPOSICAO, criar_registro, sequencia_draw,
    vertices_com_profundidade,
)
from capturar_a2c_sintetico_opengl import compilar


VERTEX_SHADER = """
#version 120
void main() {
    gl_Position = gl_Vertex;
}
"""
FRAGMENT_SHADER = """
#version 120
uniform vec4 uColor;
void main() {
    gl_FragColor = uColor;
}
"""


def _novo_fbo(GL, amostras, com_depth):
    fbo = GL.glGenFramebuffers(1)
    cor = GL.glGenRenderbuffers(1)
    depth = GL.glGenRenderbuffers(1) if com_depth else None
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, cor)
    if amostras == 4:
        GL.glRenderbufferStorageMultisample(
            GL.GL_RENDERBUFFER, 4, GL.GL_RGBA8, 64, 64
        )
    else:
        GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_RGBA8, 64, 64)
    GL.glFramebufferRenderbuffer(
        GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_RENDERBUFFER, cor
    )
    if com_depth:
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, depth)
        if amostras == 4:
            GL.glRenderbufferStorageMultisample(
                GL.GL_RENDERBUFFER, 4, GL.GL_DEPTH_COMPONENT24, 64, 64
            )
        else:
            GL.glRenderbufferStorage(
                GL.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT24, 64, 64
            )
        GL.glFramebufferRenderbuffer(
            GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT,
            GL.GL_RENDERBUFFER, depth
        )
    GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
    if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("FBO GL depth sintético incompleto")
    return fbo, cor, depth


def capturar_sobreposicao_opengl(destino_json):
    from OpenGL import GL

    destino_json = Path(destino_json)
    antigo_programa = int(GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM))
    antigo_read = int(GL.glGetIntegerv(GL.GL_READ_FRAMEBUFFER_BINDING))
    antigo_draw = int(GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING))
    antigo_rb = int(GL.glGetIntegerv(GL.GL_RENDERBUFFER_BINDING))
    antigo_view = [int(v) for v in GL.glGetIntegerv(GL.GL_VIEWPORT)]
    antiga_limpeza_cor = [float(v) for v in GL.glGetFloatv(GL.GL_COLOR_CLEAR_VALUE)]
    antiga_limpeza_z = float(GL.glGetDoublev(GL.GL_DEPTH_CLEAR_VALUE))
    antigo_depth_func = int(GL.glGetIntegerv(GL.GL_DEPTH_FUNC))
    antiga_mascara_z = bool(GL.glGetBooleanv(GL.GL_DEPTH_WRITEMASK))
    antiga_mascara_cor = [bool(v) for v in GL.glGetBooleanv(GL.GL_COLOR_WRITEMASK)]
    antigo_pack = int(GL.glGetIntegerv(GL.GL_PACK_ALIGNMENT))
    caps = (
        GL.GL_BLEND, GL.GL_DEPTH_TEST, GL.GL_STENCIL_TEST,
        GL.GL_SCISSOR_TEST, GL.GL_DITHER, GL.GL_CULL_FACE,
        GL.GL_ALPHA_TEST, GL.GL_SAMPLE_ALPHA_TO_COVERAGE, GL.GL_MULTISAMPLE,
    )
    antigas_caps = {cap: bool(GL.glIsEnabled(cap)) for cap in caps}
    vshader = fshader = program = None
    objetos = []
    controles = {}
    try:
        for cap in caps:
            GL.glDisable(cap)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glDepthFunc(GL.GL_LESS)
        GL.glColorMask(True, True, True, True)
        GL.glViewport(0, 0, 64, 64)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
        vshader = compilar(GL, GL.GL_VERTEX_SHADER, VERTEX_SHADER)
        fshader = compilar(GL, GL.GL_FRAGMENT_SHADER, FRAGMENT_SHADER)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vshader)
        GL.glAttachShader(program, fshader)
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError("Shader GL depth não linkou: " + str(
                GL.glGetProgramInfoLog(program)
            ))
        GL.glUseProgram(program)
        cor_uniform = int(GL.glGetUniformLocation(program, "uColor"))
        if cor_uniform < 0:
            raise RuntimeError("Uniform uColor ausente do shader")
        for nome, a2c, escreve_z, ordem in CASOS_SOBREPOSICAO:
            fbo, cor_rb, depth_rb = _novo_fbo(GL, 4, True)
            objetos.extend([
                ("fbo", fbo), ("rb", cor_rb), ("rb", depth_rb)
            ])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
            amostras_observadas = int(GL.glGetIntegerv(GL.GL_SAMPLES))
            if amostras_observadas != 4:
                raise RuntimeError("GL_SAMPLES diferente de 4 no FBO de profundidade")
            GL.glClearColor(0, 0, 0, 0)
            GL.glClearDepth(1.0)
            GL.glDepthMask(True)
            GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            tracos = []
            for passo in sequencia_draw(a2c, escreve_z, ordem):
                face = passo["face"]
                if face == "frente":
                    alpha = 128 / 255.0 if a2c else 1.0
                    GL.glUniform4f(cor_uniform, 1.0, 0.0, 0.0, alpha)
                else:
                    GL.glUniform4f(cor_uniform, 0.0, 0.0, 1.0, 1.0)
                GL.glDepthMask(passo["escrita_z"])
                if passo["a2c"]:
                    GL.glEnable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
                else:
                    GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
                tracos.append({
                    "face": face,
                    "a2c": bool(GL.glIsEnabled(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)),
                    "escrita_z": bool(GL.glGetBooleanv(GL.GL_DEPTH_WRITEMASK)),
                    "depth_test": bool(GL.glIsEnabled(GL.GL_DEPTH_TEST)),
                    "blend": bool(GL.glIsEnabled(GL.GL_BLEND)),
                })
                GL.glBegin(GL.GL_TRIANGLES)
                for x, y, z in vertices_com_profundidade(face):
                    # GL viewport depth=0.5*NDCz+0.5; WGPU depth=NDCz.
                    GL.glVertex3f(x, y, z * 2.0 - 1.0)
                GL.glEnd()
            GL.glDepthMask(True)
            GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
            resolve, res_cor, _ = _novo_fbo(GL, 1, False)
            objetos.extend([("fbo", resolve), ("rb", res_cor)])
            GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, fbo)
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, resolve)
            GL.glBlitFramebuffer(
                0, 0, 64, 64, 0, 0, 64, 64,
                GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST,
            )
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, resolve)
            rgba = np.frombuffer(
                bytes(GL.glReadPixels(
                    0, 0, 64, 64, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE
                )), dtype=np.uint8
            ).reshape((64, 64, 4))
            rgb = np.ascontiguousarray(np.flipud(rgba[:, :, :3]))
            arquivo = destino_json.with_name(
                destino_json.stem + "-sobreposicao-" + nome + ".png"
            )
            controles[nome] = {
                **criar_registro(
                    rgb, arquivo, nome=nome, a2c=a2c, escrita_z=escreve_z,
                    ordem=ordem, rastros=tracos
                ),
                "amostras_fbo_observadas": amostras_observadas,
                "fbo_depth_formato": "depth24",
            }
        return {
            "backend": "OpenGL",
            "tipo": "SOBREPOSICAO_DEPTH_A2C_SINTETICA",
            "controles": controles,
            "nao_homologado": True,
        }
    finally:
        GL.glUseProgram(antigo_programa)
        if program:
            GL.glDeleteProgram(program)
        if vshader:
            GL.glDeleteShader(vshader)
        if fshader:
            GL.glDeleteShader(fshader)
        for tipo, objeto in reversed(objetos):
            if tipo == "fbo":
                GL.glDeleteFramebuffers(1, [objeto])
            else:
                GL.glDeleteRenderbuffers(1, [objeto])
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, antigo_read)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, antigo_draw)
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, antigo_rb)
        GL.glViewport(*antigo_view)
        GL.glClearColor(*antiga_limpeza_cor)
        GL.glClearDepth(antiga_limpeza_z)
        GL.glDepthFunc(antigo_depth_func)
        GL.glDepthMask(antiga_mascara_z)
        GL.glColorMask(*antiga_mascara_cor)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, antigo_pack)
        for cap, habilitada in antigas_caps.items():
            (GL.glEnable if habilitada else GL.glDisable)(cap)
