"""Seleção por cor das FaceGroups da cena ORIGINAL, sem glReadPixels.

O picking usa projeção e teste de cobertura das primitivas na CPU. O resultado
mantém o contrato mh.getPickedColor() -> RGB de clrid(group), que a lógica
original de gui3d/selection.py já utiliza. Nenhuma nova ferramenta é criada.

Suporta pontos, linhas, triângulos e quads, com clipping homogêneo Vulkan.
Ainda não substitui picking de GPU; a paridade será testada.
"""

import numpy as np

from vulkan_scene import matriz_wgpu
from vulkan_displacement import posicoes_render


COR_VAZIA = (0, 0, 0)

# Volume de clip Vulkan: -w <= x,y <= w e 0 <= z <= w.
# A última restrição evita divisão por zero perto do olho da câmera.
_PLANOS_CLIP = np.asarray([
    [1, 0, 0, 1], [-1, 0, 0, 1],
    [0, 1, 0, 1], [0, -1, 0, 1],
    [0, 0, 1, 0], [0, 0, -1, 1],
    [0, 0, 0, 1],
], dtype=np.float64)
_LIMITES_CLIP = np.asarray([0, 0, 0, 0, 0, 0, 1e-6], dtype=np.float64)


def _recortar_triangulo(vertices):
    """Sutherland-Hodgman no espaço homogêneo; retorna leque triangular."""
    poligono = list(vertices)
    for plano, limite in zip(_PLANOS_CLIP, _LIMITES_CLIP):
        if not poligono:
            break
        novo = []
        anterior = poligono[-1]
        distancia_anterior = float(anterior @ plano - limite)
        for atual in poligono:
            distancia_atual = float(atual @ plano - limite)
            dentro_anterior = distancia_anterior >= 0
            dentro_atual = distancia_atual >= 0
            if dentro_anterior != dentro_atual:
                t = distancia_anterior / (distancia_anterior - distancia_atual)
                novo.append(anterior + t * (atual - anterior))
            if dentro_atual:
                novo.append(atual)
            anterior = atual
            distancia_anterior = distancia_atual
        poligono = novo
    return [np.stack((poligono[0], poligono[i], poligono[i + 1]))
            for i in range(1, len(poligono) - 1)]


def _triangulos_visiveis(clip, indices):
    """Mantém faces interiores vetorizadas e recorta apenas as de borda."""
    vertices = np.asarray(clip[indices], dtype=np.float64)
    dentro = np.all(
        vertices @ _PLANOS_CLIP.T >= _LIMITES_CLIP, axis=(1, 2)
    )
    if np.all(dentro):
        return vertices
    recortados = [trio for tri in vertices[~dentro]
                  for trio in _recortar_triangulo(tri)]
    if recortados:
        return np.concatenate((vertices[dentro], np.stack(recortados)), axis=0)
    return vertices[dentro]


def _recortar_segmento(vertices):
    """Recorta uma linha nos planos homogêneos Vulkan antes de dividir por w."""
    inicio, fim = (np.asarray(p, dtype=np.float64) for p in vertices)
    for plano, limite in zip(_PLANOS_CLIP, _LIMITES_CLIP):
        da = float(inicio @ plano - limite)
        db = float(fim @ plano - limite)
        if da < 0 and db < 0:
            return None
        if (da < 0) != (db < 0):
            t = da / (da - db)
            ponto = inicio + t * (fim - inicio)
            if da < 0:
                inicio = ponto
            else:
                fim = ponto
    return np.stack((inicio, fim))


def _profundidade_pontos_linhas(clip, indices, px, py, largura, altura):
    """Picking de GL_POINTS/GL_LINES originais via cobertura de um pixel."""
    valores = []
    for face in indices:
        if len(face) == 1:
            ponto = np.asarray(clip[int(face[0])], dtype=np.float64)
            if np.any(ponto @ _PLANOS_CLIP.T < _LIMITES_CLIP):
                continue
            ndc = ponto[:3] / ponto[3]
            sx = (ndc[0] * .5 + .5) * largura
            sy = (.5 - ndc[1] * .5) * altura
            if abs(px - sx) <= .5 and abs(py - sy) <= .5:
                valores.append(float(ndc[2]))
            continue

        if int(face[0]) == int(face[1]):
            continue
        segmento = _recortar_segmento(clip[face])
        if segmento is None:
            continue
        ndc = segmento[:, :3] / segmento[:, 3:4]
        a = np.array(((ndc[0, 0] * .5 + .5) * largura,
                      (.5 - ndc[0, 1] * .5) * altura))
        b = np.array(((ndc[1, 0] * .5 + .5) * largura,
                      (.5 - ndc[1, 1] * .5) * altura))
        vetor = b - a
        comprimento2 = float(vetor @ vetor)
        if comprimento2 <= 1e-12:
            continue
        t = float(np.clip(((px - a[0]) * vetor[0]
                           + (py - a[1]) * vetor[1]) / comprimento2,
                          0.0, 1.0))
        proximo = a + vetor * t
        if float(np.sum((proximo - (px, py)) ** 2)) <= .25:
            valores.append(float(ndc[0, 2] * (1.0 - t) + ndc[1, 2] * t))
    profundidades = [z for z in valores if 0.0 <= z <= 1.0]
    return min(profundidades) if profundidades else None


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


def _selecionar_cor_e_profundidade(mundo, cameras, x, y, largura, altura):
    """Calcula grupo visível e profundidade do pixel via cena original.

    O pipeline de seleção original desenha só objetos .pickable, com sua
    própria matriz de câmera e grupos de face. A prioridade da cena é
    respeitada e a profundidade menor vence.
    """
    if (x is None or y is None or largura <= 0 or altura <= 0
            or not (0 <= x < largura and 0 <= y < altura)):
        return COR_VAZIA, 1.0
    if mundo is None or cameras is None:
        return COR_VAZIA, 1.0

    px, py = float(x) + 0.5, float(y) + 0.5
    melhor_z = float("inf")
    resultado = COR_VAZIA
    for obj in sorted(mundo, key=lambda item: item.priority):
        if not obj.visibility or not obj.pickable:
            continue
        coords = posicoes_render(obj)
        if coords.ndim != 2 or coords.shape[1] != 3 or not len(coords):
            continue
        face = np.asarray(obj.primitives)
        if face.ndim != 2 or face.shape[1] not in (1, 2, 3, 4):
            continue
        mvp = matriz_wgpu(cameras[obj.cameraMode], obj)
        vertices = np.concatenate((
            coords, np.ones((len(coords), 1), dtype=np.float32),
        ), axis=1)
        clip = vertices @ mvp.T
        for i, (inicio, quantidade) in enumerate(obj.groups):
            if face.shape[1] in (1, 2):
                indices = np.asarray(
                    face[inicio:inicio + quantidade], dtype=np.int64,
                )
                if not len(indices):
                    continue
                if np.any(indices < 0) or np.any(indices >= len(coords)):
                    raise ValueError("Índice de face fora da malha do MakeHuman")
                z = _profundidade_pontos_linhas(
                    clip, indices, px, py, largura, altura,
                )
                if z is not None and z < melhor_z:
                    melhor_z = z
                    resultado = tuple(int(v) for v in obj.clrid(i))
                continue
            tri = _segmentos_faces(face, inicio, quantidade)
            if not len(tri):
                continue
            if np.any(tri < 0) or np.any(tri >= len(coords)):
                raise ValueError("Índice de face fora da malha do MakeHuman")
            # Recortar antes da divisão por w mantém a parte visível
            # mesmo quando um vértice passa pelo plano próximo.
            p = _triangulos_visiveis(clip, tri)
            if not len(p):
                continue
            p = p[:, :, :3] / p[:, :, 3:4]
            p[:, :, 0] = (p[:, :, 0] * 0.5 + 0.5) * largura
            p[:, :, 1] = (0.5 - p[:, :, 1] * 0.5) * altura
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
    return resultado, (melhor_z if np.isfinite(melhor_z) else 1.0)


def selecionar_cor(mundo, cameras, x, y, largura, altura):
    """RGB do grupo selecionado, compatível com mh.getPickedColor()."""
    cor, _ = _selecionar_cor_e_profundidade(
        mundo, cameras, x, y, largura, altura,
    )
    return cor


def selecionar_profundidade(mundo, cameras, x, y, largura, altura):
    """Z do pixel [0,1] para o contrato camera.convertToWorld3D()."""
    _, z = _selecionar_cor_e_profundidade(
        mundo, cameras, x, y, largura, altura,
    )
    return z
