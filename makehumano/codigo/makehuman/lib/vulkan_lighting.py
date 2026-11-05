"""Parâmetros de iluminação da cena original para o shader WGSL.

Suporta a luz ambiente e até oito luzes pontuais, como glmodule antigo.
Mantém iluminação dependente da geometria 3D sem importar OpenGL.
O modelo especular/atenuação do MakeHuman ainda precisa de equivalência.
"""

import numpy as np


def _rgb(valor, nome):
    valor = np.asarray(getattr(valor, "values", valor), dtype=np.float32)
    if valor.shape != (3,) or not np.isfinite(valor).all():
        raise ValueError(f"{nome}: RGB inválido na cena original")
    return valor


def dados_iluminacao_cena(cena):
    """Retorna ambiente vec4 e arrays vec4 de posição/cor de oito luzes.

    Dados permanecem com alinhamento de 16 bytes para os uniforms WebGPU.
    """
    ambiente = np.array([0.3, 0.3, 0.3, 0.0], dtype=np.float32)
    posicoes = np.zeros((8, 4), dtype=np.float32)
    cores = np.zeros((8, 4), dtype=np.float32)
    if cena is None:
        return ambiente, posicoes, cores, 0

    ambiente[:3] = _rgb(cena.environment.ambience, "Ambiente")
    luzes = list(cena.lights)[:8]
    for indice, luz in enumerate(luzes):
        posicao = np.asarray(luz.position, dtype=np.float32)
        if posicao.shape != (3,) or not np.isfinite(posicao).all():
            raise ValueError("Posição de luz inválida na cena original")
        posicoes[indice, :3] = posicao
        posicoes[indice, 3] = 1.0
        cores[indice, :3] = _rgb(luz.color, "Luz")
        cores[indice, 3] = 1.0
    return ambiente, posicoes, cores, len(luzes)
