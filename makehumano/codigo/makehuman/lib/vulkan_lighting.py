"""Parâmetros de iluminação da cena original para o shader WGSL.

Suporta a luz ambiente e até oito luzes pontuais, como glmodule antigo.
Mantém iluminação dependente da geometria 3D sem importar OpenGL.
Preserva cores especulares e aplica foco, ângulo e atenuação do editor.
Amostras de área são fornecidas pelo adaptador Vulkan; sombras pendentes.
"""

import numpy as np


def _rgb(valor, nome):
    valor = np.asarray(getattr(valor, "values", valor), dtype=np.float32)
    if valor.shape != (3,) or not np.isfinite(valor).all():
        raise ValueError(f"{nome}: RGB inválido na cena original")
    return valor


def dados_iluminacao_cena(cena, limite=8):
    """Retorna ambiente vec4 e arrays vec4 de posição/cor de oito luzes.

    Dados permanecem com alinhamento de 16 bytes para os uniforms WebGPU.
    """
    ambiente = np.array([0.3, 0.3, 0.3, 0.0], dtype=np.float32)
    posicoes = np.zeros((limite, 4), dtype=np.float32)
    cores = np.zeros((limite, 4), dtype=np.float32)
    if cena is None:
        return ambiente, posicoes, cores, 0

    ambiente[:3] = _rgb(cena.environment.ambience, "Ambiente")
    luzes = list(cena.lights)[:limite]
    for indice, luz in enumerate(luzes):
        posicao = np.asarray(luz.position, dtype=np.float32)
        if posicao.shape != (3,) or not np.isfinite(posicao).all():
            raise ValueError("Posição de luz inválida na cena original")
        posicoes[indice, :3] = posicao
        posicoes[indice, 3] = 1.0
        cores[indice, :3] = _rgb(luz.color, "Luz")
        cores[indice, 3] = 1.0
    return ambiente, posicoes, cores, len(luzes)


def cores_especulares_cena(cena, limite=8):
    """Conservar a cor especular independente de Light.color (.mhscene v5)."""
    cores = np.zeros((limite, 4), dtype=np.float32)
    if cena is None:
        return cores
    for indice, luz in enumerate(list(cena.lights)[:limite]):
        # Objetos de teste/integrações anteriores podem ter somente color.
        cores[indice, :3] = _rgb(getattr(luz, "specular", luz.color), "Luz especular")
        cores[indice, 3] = 1.0
    return cores


def parametros_foco_atenuacao(cena, limite=8):
    """Direção/cosseno do cone e atenuação quadrática das luzes originais.

    fov é o ângulo total do cone em graus; 180 mantém a luz pontual sem cone.
    attenuation=0 mantém intensidade constante, como nas cenas anteriores.
    """
    directions = np.zeros((limite, 4), np.float32)
    directions[:, 3] = -1.0
    parameters = np.zeros((limite, 4), np.float32)
    if cena is None:
        return directions, parameters
    for index, light in enumerate(list(cena.lights)[:limite]):
        attenuation = float(getattr(light, "attenuation", 0.0))
        angle = float(getattr(light, "fov", 180.0))
        if not np.isfinite(attenuation) or attenuation < 0:
            raise ValueError("Atenuação da luz deve ser finita e não negativa")
        if not np.isfinite(angle):
            raise ValueError("Ângulo de foco da luz deve ser finito")
        angle = float(np.clip(angle, 0, 180))
        parameters[index, 0] = attenuation
        parameters[index, 1] = float(getattr(light, "_peso_vulkan", 1.))
        if angle < 180:
            position = _rgb(light.position, "Posição da luz")
            focus = _rgb(getattr(light, "focus", (0, 0, 0)), "Foco da luz")
            direction = focus - position
            length = float(np.linalg.norm(direction))
            if length < 1e-8:
                raise ValueError("Foco e posição coincidem em luz com cone ativo")
            directions[index, :3] = direction / length
            directions[index, 3] = np.cos(np.deg2rad(angle * .5))
    return directions, parameters
