"""Amostragem determinística dos emissores do editor de cena original."""
from types import SimpleNamespace
import numpy as np

MAX_LUZES_ORIGINAIS = 8
MAX_AMOSTRAS_AREA = 16
MAX_LUZES_VULKAN = MAX_LUZES_ORIGINAIS * MAX_AMOSTRAS_AREA


def _vetor(value, name):
    value = np.asarray(value, dtype=np.float64)
    if value.shape != (3,) or not np.isfinite(value).all():
        raise ValueError(f"{name}: vetor de luz inválido")
    return value


def amostrar_luzes(cena):
    """Expandir até oito emissores, conservando sua energia e a cena fonte.

    A viewport limita cada área a 16 amostras. O valor original de Samples
    permanece intacto para salvar/exportar a cena. Tamanho zero e Samples=1
    produzem exatamente a luz pontual anterior. Não calcula oclusão/sombras.
    """
    if cena is None:
        return None, 0
    lights = []
    first_count = 0
    for index, light in enumerate(list(cena.lights)[:MAX_LUZES_ORIGINAIS]):
        requested = float(getattr(light, "areaLights", 1))
        if not np.isfinite(requested) or requested < 1 or requested != int(requested):
            raise ValueError("Samples da luz deve ser um inteiro positivo")
        count = min(int(requested), MAX_AMOSTRAS_AREA)
        position = _vetor(light.position, "Posição")
        focus = _vetor(getattr(light, "focus", (0., 0., 0.)), "Foco")
        offsets = np.zeros((1, 3), dtype=np.float64)
        if count > 1:
            size = float(getattr(light, "areaLightSize", 4.))
            if not np.isfinite(size) or size < 0:
                raise ValueError("Softness da luz deve ser finito e não negativo")
            if size > 0:
                normal = focus - position
                length = np.linalg.norm(normal)
                normal = normal / length if length > 1e-8 else np.array([0., 0., -1.])
                helper = np.eye(3)[np.argmin(np.abs(normal))]
                u = np.cross(normal, helper)
                u /= np.linalg.norm(u)
                v = np.cross(normal, u)
                # Pares opostos mantêm o centro e a energia, inclusive para
                # números não quadrados de amostras, sem ruído entre frames.
                pairs = count // 2
                xy = np.mod((np.arange(pairs)[:, None] + .5)
                            * np.array([.754877666, .569840291]), 1.) - .5
                xy = np.concatenate((xy, -xy))
                if count % 2:
                    xy = np.concatenate((xy, np.zeros((1, 2))))
                offsets = size * (xy[:, :1] * u + xy[:, 1:] * v)
        count = len(offsets)
        if index == 0:
            first_count = count
        for offset in offsets:
            lights.append(SimpleNamespace(
                position=position + offset, focus=focus,
                color=light.color, specular=getattr(light, "specular", light.color),
                fov=getattr(light, "fov", 180.), attenuation=getattr(light, "attenuation", 0.),
                _peso_vulkan=1. / count,
            ))
    return SimpleNamespace(environment=cena.environment, lights=lights), first_count
