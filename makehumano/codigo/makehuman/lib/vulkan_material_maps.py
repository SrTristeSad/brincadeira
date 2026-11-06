"""Mapas do Material original, compartilhados pelo raster e shader Vulkan."""
import math
import os

_MAPAS = {
    "displacement": ("displacement", "displacementMapTexture", "displacementmapTexture", "displacementMapIntensity", "displacementmapIntensity"),
    "ao": ("ambientOcclusion", "aoMapTexture", "aomapTexture", "aoMapIntensity", "aomapIntensity"),
    "bump": ("bump", "bumpMapTexture", "bumpmapTexture", "bumpMapIntensity", "bumpmapIntensity"),
    "specular": ("spec", "specularMapTexture", "specularmapTexture", "specularMapIntensity", "specularmapIntensity"),
    "transparency": ("transparency", "transparencyMapTexture", "transparencymapTexture", "transparencyMapIntensity", "transparencymapIntensity"),
}


def parametros_mapa(material, tipo):
    """Retornar recurso e força 0..1, respeitando os controles .mhmat.

    Força zero/configuração desligada não carrega recursos. Um mapa ativo
    ausente é um erro explícito, não uma textura branca substituta.
    """
    if material is None:
        return None, 0.0
    config_key, attr, param, intensity_attr, intensity_param = _MAPAS[tipo]
    config = getattr(material, "shaderConfig", {}) or {}
    if not config.get(config_key, True):
        return None, 0.0
    params = getattr(material, "shaderParameters", {}) or {}
    texture = params.get(param)
    if texture is None:
        texture = getattr(material, attr, None)
    if texture is None and tipo == "ao":
        texture = params.get("ambientOcclusionMap")
    if texture is None:
        return None, 0.0
    value = params.get(intensity_param, getattr(material, intensity_attr, 1.0))
    if isinstance(value, (tuple, list)):
        if len(value) != 1:
            raise ValueError(f"Mapa {tipo}: intensidade deve ser escalar")
        value = value[0]
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"Mapa {tipo}: intensidade não finita")
    value = min(1.0, max(0.0, value))
    if value == 0.0:
        return None, 0.0
    if isinstance(texture, (str, os.PathLike)) and not os.path.isfile(texture):
        raise ValueError(f"Mapa {tipo}: textura não encontrada: {os.fspath(texture)}")
    return texture, value


def mapa_transparencia_ativo(material):
    return parametros_mapa(material, "transparency")[0] is not None
