"""Captura OpenGL legada: duas faces coplanares (e quase) com MSAA4×.

FBO de cor+depth24 real, readback por resolve e PNGs RGB8. Não altera o
MakeHuman de produção, nem sua projeção, materiais ou malhas.
"""
from pathlib import Path
import numpy as np

from capturar_a2c_sintetico_opengl import compilar
from capturar_sobreposicao_depth_opengl import (
    FRAGMENT_SHADER, VERTEX_SHADER, _novo_fbo,
)
from contrato_coplanares_depth_sintetica import (
    CASOS_COPLANARES, passos_desenho, registrar_captura, vertices_face,
)


def capturar_coplanares_opengl(destino_json):
    from OpenGL import GL
    destino_json = Path(destino_json)
    original_programa = int(GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM))
    original_read = int(GL.glGetIntegerv(GL.GL_READ_FRAMEBUFFER_BINDING))
    original_draw = int(GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING))
    original_rb = int(GL.glGetIntegerv(GL.GL_RENDERBUFFER_BINDING))
    original_view = [int(x) for x in GL.glGetIntegerv(GL.GL_VIEWPORT)]
    original_clear_cor = [float(x) for x in GL.glGetFloatv(GL.GL_COLOR_CLEAR_VALUE)]
    original_clear_depth = float(GL.glGetDoublev(GL.GL_DEPTH_CLEAR_VALUE))
    original_depth_range = [float(x) for x in GL.glGetDoublev(GL.GL_DEPTH_RANGE)]
    original_depth_func = int(GL.glGetIntegerv(GL.GL_DEPTH_FUNC))
    original_mask_depth = bool(GL.glGetBooleanv(GL.GL_DEPTH_WRITEMASK))
    original_mask_cor = [bool(x) for x in GL.glGetBooleanv(GL.GL_COLOR_WRITEMASK)]
    original_pack = int(GL.glGetIntegerv(GL.GL_PACK_ALIGNMENT))
    flags = (
        GL.GL_BLEND, GL.GL_DEPTH_TEST, GL.GL_STENCIL_TEST,
        GL.GL_SCISSOR_TEST, GL.GL_DITHER, GL.GL_CULL_FACE,
        GL.GL_ALPHA_TEST, GL.GL_SAMPLE_ALPHA_TO_COVERAGE, GL.GL_MULTISAMPLE,
        GL.GL_SAMPLE_COVERAGE, GL.GL_POLYGON_OFFSET_FILL,
    )
    original_flags = {cap: bool(GL.glIsEnabled(cap)) for cap in flags}
    vertex = fragment = programa = None
    objetos = []
    controles = {}
    try:
        for cap in flags:
            GL.glDisable(cap)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glDepthRange(0.0, 1.0)
        GL.glColorMask(True, True, True, True)
        GL.glViewport(0, 0, 64, 64)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
        vertex = compilar(GL, GL.GL_VERTEX_SHADER, VERTEX_SHADER)
        fragment = compilar(GL, GL.GL_FRAGMENT_SHADER, FRAGMENT_SHADER)
        programa = GL.glCreateProgram()
        GL.glAttachShader(programa, vertex)
        GL.glAttachShader(programa, fragment)
        GL.glLinkProgram(programa)
        if not GL.glGetProgramiv(programa, GL.GL_LINK_STATUS):
            raise RuntimeError("GLSL coplanar não linkou: " + str(
                GL.glGetProgramInfoLog(programa)
            ))
        GL.glUseProgram(programa)
        uniform = int(GL.glGetUniformLocation(programa, "uColor"))
        if uniform < 0:
            raise RuntimeError("Uniform uColor coplanar ausente")

        for caso in CASOS_COPLANARES:
            nome, compare, a2c, z_write, ordem, separacao = caso
            fbo, cor_rb, depth_rb = _novo_fbo(GL, 4, True)
            objetos.extend((("fbo", fbo), ("rb", cor_rb), ("rb", depth_rb)))
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
            numero_amostras = int(GL.glGetIntegerv(GL.GL_SAMPLES))
            if numero_amostras != 4:
                raise RuntimeError("GL_SAMPLES diferente de 4 no probe coplanar")
            GL.glDepthFunc(GL.GL_LESS if compare == "less" else GL.GL_LEQUAL)
            GL.glClearColor(0.0, 0.0, 0.0, 0.0)
            GL.glClearDepth(1.0)
            GL.glDepthMask(True)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            observado = []
            for passo in passos_desenho(compare, a2c, z_write, ordem):
                face = passo["face"]
                alpha = 128 / 255.0 if face == "vermelho" and a2c else 1.0
                if face == "vermelho":
                    GL.glUniform4f(uniform, 1.0, 0.0, 0.0, alpha)
                else:
                    GL.glUniform4f(uniform, 0.0, 0.0, 1.0, 1.0)
                GL.glDepthMask(passo["escrita_z"])
                if passo["a2c"]:
                    GL.glEnable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
                else:
                    GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
                observed_func = int(GL.glGetIntegerv(GL.GL_DEPTH_FUNC))
                observado.append({
                    "face": face,
                    "a2c": bool(GL.glIsEnabled(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)),
                    "escrita_z": bool(GL.glGetBooleanv(GL.GL_DEPTH_WRITEMASK)),
                    "depth_compare": (
                        "less" if observed_func == GL.GL_LESS else
                        "less-equal" if observed_func == GL.GL_LEQUAL else
                        "invalido"
                    ),
                    "depth_test": bool(GL.glIsEnabled(GL.GL_DEPTH_TEST)),
                    "blend": bool(GL.glIsEnabled(GL.GL_BLEND)),
                })
                GL.glBegin(GL.GL_TRIANGLES)
                for x, y, z in vertices_face(face, separacao):
                    # Normalizar z: GL clip [-1,1] → window depth [0,1].
                    GL.glVertex3f(x, y, 2.0 * z - 1.0)
                GL.glEnd()
            GL.glDepthMask(True)
            GL.glDisable(GL.GL_SAMPLE_ALPHA_TO_COVERAGE)
            resolvido, resolve_rb, _ = _novo_fbo(GL, 1, False)
            objetos.extend((("fbo", resolvido), ("rb", resolve_rb)))
            GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, fbo)
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, resolvido)
            GL.glBlitFramebuffer(
                0, 0, 64, 64, 0, 0, 64, 64,
                GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST
            )
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, resolvido)
            rgba = np.frombuffer(
                bytes(GL.glReadPixels(
                    0, 0, 64, 64, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE
                )), dtype=np.uint8
            ).reshape(64, 64, 4)
            rgb = np.ascontiguousarray(np.flipud(rgba[:, :, :3]))
            png = destino_json.with_name(
                destino_json.stem + "-coplanar-" + nome + ".png"
            )
            controles[nome] = {
                **registrar_captura(rgb, png, caso, observado),
                "amostras_fbo_observadas": numero_amostras,
                "formato_depth_fbo": "depth24",
                "depth_range": [0.0, 1.0],
                "nota_estados": "Depth compare e A2C lidos via glGet/glIsEnabled",
            }
        return {
            "tipo": "COPLANARES_MSAA_Z_4X",
            "backend": "OpenGL",
            "controles": controles,
            "nao_homologado": True,
        }
    finally:
        GL.glUseProgram(original_programa)
        if programa:
            GL.glDeleteProgram(programa)
        if vertex:
            GL.glDeleteShader(vertex)
        if fragment:
            GL.glDeleteShader(fragment)
        for tipo, obj in reversed(objetos):
            if tipo == "fbo":
                GL.glDeleteFramebuffers(1, [obj])
            elif obj is not None:
                GL.glDeleteRenderbuffers(1, [obj])
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, original_read)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, original_draw)
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, original_rb)
        GL.glViewport(*original_view)
        GL.glClearColor(*original_clear_cor)
        GL.glClearDepth(original_clear_depth)
        GL.glDepthRange(*original_depth_range)
        GL.glDepthFunc(original_depth_func)
        GL.glDepthMask(original_mask_depth)
        GL.glColorMask(*original_mask_cor)
        GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, original_pack)
        for cap, enabled in original_flags.items():
            (GL.glEnable if enabled else GL.glDisable)(cap)
