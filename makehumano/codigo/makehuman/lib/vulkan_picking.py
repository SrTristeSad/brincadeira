"""Seleção por cor das FaceGroups da cena ORIGINAL, sem glReadPixels.

A fase piloto usa interseção de triângulos projetados na CPU. O resultado
mantém o contrato mh.getPickedColor() -> RGB de clrid(group), que a lógica
original de gui3d/selection.py já utiliza. Nenhuma nova ferramenta é criada.

Limitado a triângulos/quads, sem clipping de primitivas que cruzam near plane.
Não é substituto definitivo do picking da GPU; a paridade será testada.
"""

import numpy as np

from vulkan_scene import matriz_wgpu


COR_VAZIA = (0, 0, 0)


def _segmentos_faces(face, start, count):
    """Triangula preservando o grupo e descartando faces degeneradas."""
    dados = np.asarray(face[start:start + count])
    if dados.size == 0:
        return np.empty((0, 3), dtype=np.int64)
    if dados.ndim != 2 or dados.shape[1] not in (3, 4):
        return np.empty((0, 3), dtype=np.int64)
    if dados.shape[1] == 4:
        tris = np.concatenate(
            (dados[:, (0, 1, 2)], dados[:, (0, 2, 3)]), axis=0,
        )
    else:
        tris = dados
    ok = ((tris[:, 0] != tris[:, 1])
          & (tris[:, 1] != tris[:, 2])
          & (tris[:, 0] != tris[:, 2]))
    return np.asarray(tris[ok], dtype=np.int64)


def selecionar_cor(mundo, cameras, x, y, largura, altura):
    """Retorna RGB da FaceGroup visível sob pixel Qt (origem superior).

    O pipeline de seleção original desenha só objetos .pickable, com sua
    própria matriz de câmera e grupos de face. A prioridade da cena é
    respeitada e a profundidade menor vence.
    """
    if (x is None or y is None or largura <= 0 or altura <= 0
            or not (0 <= x < largura and 0 <= y < altura)):
        return COR_VAZIA
    if mundo is None or cameras is None:
        return COR_VAZIA

    px, py = float(x) + 0.5, float(y) + 0.5
    melhor_z = float("inf")
    resultado = COR_VAZIA
    for obj in sorted(mundo, key=lambda item: item.priority):
        if not obj.visibility or not obj.pickable:
            continue
        coords = np.asarray(obj.verts, dtype=np.float32)
        if coords.ndim != 2 or coords.shape[1] != 3 or not len(coords):
            continue
        face = np.asarray(obj.primitives)
        if face.ndim != 2 or face.shape[1] not in (3, 4):
            continue
        mvp = matriz_wgpu(cameras[obj.cameraMode], obj)
        vertices = np.concatenate((
            coords, np.ones((len(coords), 1), dtype=np.float32),
        ), axis=1)
        clip = vertices @ mvp.T
        valido = clip[:, 3] > 1e-6
        pontos = np.zeros((len(coords), 3), dtype=np.float32)
        pontos[valido] = clip[valido, :3] / clip[valido, 3:4]
        pontos[:, 0] = (pontos[:, 0] * 0.5 + 0.5) * largura
        pontos[:, 1] = (0.5 - pontos[:, 1] * 0.5) * altura

        for i, (inicio, quantidade) in enumerate(obj.groups):
            tri = _segmentos_faces(face, inicio, quantidade)
            if not len(tri):
                continue
            if np.any(tri < 0) or np.any(tri >= len(coords)):
                raise ValueError("Índice de face fora da malha do MakeHuman")
            # Não usar pontos atrás da câmera ou antes do plano próximo.
            tri = tri[np.all(valido[tri], axis=1)]
            if not len(tri):
                continue
            p = pontos[tri]
            ax, ay = p[:, 0, 0], p[:, 0, 1]
            bx, by = p[:, 1, 0], p[:, 1, 1]
            cx, cy = p[:, 2, 0], p[:, 2, 1]
            area = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            ok = np.abs(area) > 1e-10
            if getattr(obj, "cull", 0) > 0:
                ok &= area < 0  # frente CCW em coordenadas NDC y-up
            elif getattr(obj, "cull", 0) < 0:
                ok &= area > 0
            if not np.any(ok):
                continue
            a = np.zeros(len(p), np.float32)
            b = np.zeros(len(p), np.float32)
            a[ok] = ((by[ok] - cy[ok]) * (px - cx[ok])
                     + (cx[ok] - bx[ok]) * (py - cy[ok])) / area[ok]
            b[ok] = ((cy[ok] - ay[ok]) * (px - cx[ok])
                     + (ax[ok] - cx[ok]) * (py - cy[ok])) / area[ok]
            d = 1.0 - a - b
            dentro = ok & (a >= -1e-6) & (b >= -1e-6) & (d >= -1e-6)
            if not np.any(dentro):
                continue
            profundidade = (
                a * p[:, 0, 2] + b * p[:, 1, 2] + d * p[:, 2, 2]
            )
            dentro &= (profundidade >= 0) & (profundidade <= 1)
            if not np.any(dentro):
                continue
            menor = float(np.min(profundidade[dentro]))
            if menor < melhor_z:
                melhor_z = menor
                resultado = tuple(int(v) for v in obj.clrid(i))
    return resultado
