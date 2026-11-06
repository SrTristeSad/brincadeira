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


def configuracao_shader_nativo(material):
    """Resolve presets GLSL originais portados explicitamente para WGSL.

    Retorna (modo, controles, nome_pendente). Não compila nem interpreta GLSL.
    mode 0 = shader de material padrão; mode 1 = xray original.
    Um preset desconhecido fica identificado como pendente, sem fingir
    que foi convertido.
    """
    import math

    caminho = getattr(material, "shader", None)
    if not caminho:
        return 0, (0.0, 0.0, 0.0, 0.0), None
    normalizado = str(caminho).replace("\\", "/").lower().rstrip("/")
    nome = normalizado.rsplit("/", 1)[-1]
    # Só roteamos nomes da família oficial de shaders incorporados.
    if "/shaders/glsl/" not in normalizado:
        return 0, (0.0, 0.0, 0.0, 0.0), normalizado
    if nome != "xray":
        return 0, (0.0, 0.0, 0.0, 0.0), nome

    parametros = getattr(material, "shaderParameters", {}) or {}
    def escalar(chave, padrao):
        valor = parametros.get(chave, padrao)
        if isinstance(valor, (list, tuple)) and len(valor) == 1:
            valor = valor[0]
        n = float(valor)
        if not math.isfinite(n):
            raise ValueError("Shader xray: parâmetro não finito: " + chave)
        return n

    cor = getattr(material, "ambientColor", None)
    cor = getattr(cor, "values", cor)
    if cor is None:
        cor = (0.1, 0.1, 0.1)
    if len(cor) != 3 or not all(math.isfinite(float(v)) for v in cor):
        raise ValueError("Shader xray: ambientColor RGB inválido")
    ambiente = sum(float(v) for v in cor) / 3.0
    config = getattr(material, "shaderConfig", {}) or {}
    vertex = float(bool(config.get("vertexColors", False)))
    return (
        1,
        (
            float(ambiente),
            max(0.0, escalar("edgefalloff", 1.0)),
            escalar("intensity", 0.7),
            vertex,
        ),
        None,
    )
