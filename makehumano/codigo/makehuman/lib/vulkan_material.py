"""Parâmetros básicos dos materiais da viewport Vulkan do MakeHuman original.

Reaproveita configurações e cores já existentes em lib/object3d.Object3D.
Não cria materiais próprios: shaders específicos, transparência e o modo
wireframe completo ainda exigem equivalência com o motor OpenGL original.
"""

import numpy as np


def parametros_material_vulkan(obj):
    """Retorna (cor RGBA + flags para uniform GPU, caminho de textura).

    Layout das duas vec4 após a matriz MVP:
      cor: diffuseColor RGB e opacity do material original
      flags.x: 1 para objeto shadeless, 0 para iluminação do piloto

    Objetos que não usam textura difusa não devem amostrar o arquivo,
    mesmo que haja um caminho de textura associado ao objeto.
    """
    solido = bool(obj.solid)
    if solido:
        material = obj.material
        difusa = np.asarray(material.diffuseColor.values, dtype=np.float32)
        opacidade = float(material.opacity)
        if difusa.shape != (3,) or not np.isfinite(difusa).all():
            raise ValueError("Cor difusa do MakeHuman inválida")
        if not np.isfinite(opacidade) or not 0 <= opacidade <= 1:
            raise ValueError("Opacidade do MakeHuman inválida")
    else:
        # glmodule usa material branco para objetos não sólidos.
        difusa = np.ones(3, dtype=np.float32)
        opacidade = 1.0

    resultado = np.asarray([
        float(difusa[0]), float(difusa[1]), float(difusa[2]), opacidade,
        float(bool(obj.shadeless)), 0.0, 0.0, 0.0,
    ], dtype=np.float32)

    caminho = obj.texture if (solido and bool(obj.isTextured)) else None
    return resultado, caminho
