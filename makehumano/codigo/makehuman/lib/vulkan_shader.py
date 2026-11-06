"""Interface provisória de shaders do MakeHuman no backend Vulkan.

Shaders GLSL legados não podem ser executados diretamente por WebGPU.
A pipeline Vulkan interna é construída em vulkan_scene.py. Não anunciar
suporte a shaders personalizados enquanto ainda não foram convertidos.
"""


# Apenas presets portados e testados entram no seletor original.
# Shader.supported() continua False: isso descreve compilação de GLSL,
# que ainda não existe em Vulkan.
PRESETS_NATIVOS = frozenset(("xray", "litsphere", "phong", "toon", "normalmap"))


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
    mode 0 = material padrão; 1 = xray; 2 = litsphere; 3 = phong;
    mode 4 = toon; 5 = normalmap. Controles extras em função separada.
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
    if nome == "normalmap":
        # A geometria mantém o tangent space no fragmento Vulkan,
        # enquanto os parâmetros da cena continuam os do MakeHuman.
        return 5, (0.0, 0.0, 0.0, 0.0), None
    if nome == "phong":
        ambient = getattr(material, "ambientColor", None)
        rgb = getattr(ambient, "values", ambient)
        if rgb is None:
            rgb = (0.2, 0.2, 0.2)
        if len(rgb) != 3 or not all(math.isfinite(float(c)) for c in rgb):
            raise ValueError("Shader phong: ambientColor RGB inválido")
        return 3, tuple(float(v) for v in rgb) + (0.0,), None
    if nome == "toon":
        return 4, tuple(
            _parametro_numerico(parametros, key, default, nome)
            for key, default in (
                ("silhouetteThreshold", 0.2),
                ("shininess", 20.0),
                ("ambientIntensity", 0.4),
                ("specularIntensity", 0.2),
            )
        ), None
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



def _parametro_numerico(parametros, chave, padrao, nome_shader):
    """Lê um parâmetro escalar do material original (incluindo listas .mhmat)."""
    import math

    valor = parametros.get(chave, padrao)
    if isinstance(valor, (list, tuple)):
        if len(valor) != 1:
            raise ValueError("Shader " + nome_shader + ": vetor inválido: " + chave)
        valor = valor[0]
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError("Shader " + nome_shader + ": " + chave + " não finito")
    return numero


def parametros_extras_shader_nativo(material):
    """Quatro floats extras WGSL; toon usa três controles de iluminação."""
    caminho = getattr(material, "shader", None)
    if nome_preset_nativo(caminho) != "toon":
        return (0.0, 0.0, 0.0, 0.0)
    parametros = getattr(material, "shaderParameters", {}) or {}
    return (
        _parametro_numerico(parametros, "diffuseIntensity", 0.4, "toon"),
        _parametro_numerico(parametros, "specular_th", 0.3, "toon"),
        _parametro_numerico(parametros, "diffuse_th", 0.5, "toon"),
        0.0,
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


def textura_normalmap_nativa(material):
    """Obtém o mapa de normais do preset original, sem fallback branco."""
    import os

    if material is None:
        return None
    parametros = getattr(material, "shaderParameters", {}) or {}
    textura = parametros.get("normalmapTexture") or getattr(
        material, "normalMapTexture", None
    )
    if not textura:
        return None
    if isinstance(textura, (str, os.PathLike)) and not os.path.isfile(textura):
        raise ValueError(
            "Shader normalmap: textura de normais não encontrada: "
            + os.fspath(textura)
        )
    return textura
