"""Interface provisória de shaders do MakeHuman no backend Vulkan.

Shaders GLSL legados não podem ser executados diretamente por WebGPU.
A pipeline Vulkan interna é construída em vulkan_scene.py. Não anunciar
suporte a shaders personalizados enquanto ainda não foram convertidos.
"""


class Shader:
    @classmethod
    def supported(cls):
        return False

    @classmethod
    def glslVersionStr(cls):
        return ""

    @classmethod
    def glslVersion(cls):
        return (0, 0)

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Shaders GLSL personalizados ainda não foram migrados para WGSL"
        )
