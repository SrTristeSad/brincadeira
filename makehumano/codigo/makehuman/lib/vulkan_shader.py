"""Interface provisória de shaders do MakeHuman no backend Vulkan.

Shaders GLSL legados não podem ser executados diretamente por WebGPU.
A pipeline Vulkan interna é construída em vulkan_scene.py. Não anunciar
suporte a shaders personalizados enquanto ainda não foram convertidos.
"""


# Apenas presets portados e testados entram no seletor original.
# Shader.supported() continua False: isso descreve compilação de GLSL,
# que ainda não existe em Vulkan.
PRESETS_NATIVOS = frozenset(("xray", "litsphere"))


def nome_preset_nativo(caminho):
    """Nome oficial de um preset WGSL, sem aceitar GLSL arbitrário."""
    if not caminho:
        return None
    normalizado = str(caminho).replace("\\", "/").lower().rstrip("/")
    if "/shaders/glsl/" not in normalizado:
        return None
    nome = normalizado.rsplit("/", 1)[-1]
    return nome if nome in PRESETS_NATIVOS else None


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
    mode 0 = shader de material padrão; 1 = xray; 2 = litsphere.
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
    if nome_preset_nativo(caminho) is None:
        return 0, (0.0, 0.0, 0.0, 0.0), nome

    parametros = getattr(material, "shaderParameters", {}) or {}
    if nome == "litsphere":
        aditivo = parametros.get("AdditiveShading", 0.0)
        if isinstance(aditivo, (tuple, list)) and len(aditivo) == 1:
            aditivo = aditivo[0]
        aditivo = float(aditivo)
        if not math.isfinite(aditivo):
            raise ValueError("Shader litsphere: AdditiveShading não finito")
        config = getattr(material, "shaderConfig", {}) or {}
        return (
            2, (
                float(max(0.0, min(1.0, aditivo))),
                float(bool(config.get("vertexColors", False))),
                float(bool(config.get("diffuse", False))),
                0.0,
            ),
            None,
        )
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


def textura_litsphere_nativa(material):
    """Obtém imagem ou caminho da LitSphere pelos parâmetros do .mhmat.

    Em autoBlendSkin, o getter do Material produz a imagem atual do
    EthnicSkinBlender original, sem armazenar nova identidade de personagem.
    """
    if material is None:
        return None
    parametros = getattr(material, "shaderParameters", {}) or {}
    return parametros.get("litsphereTexture")
