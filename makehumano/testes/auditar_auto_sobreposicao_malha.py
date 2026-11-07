"""Auditoria CPU independente: triângulos da malha real projetados sobre Z-delta.

Recebe Object3D/câmera e as DUAS capturas da mesma GUI; não altera
renderizador. A contagem refere-se a candidatos geométricos no centro
de pixels (sem culling, alpha test ou amostras MSAA individuais).
Nunca é evidência suficiente de overdraw ou de visibilidade efetiva.
"""
import hashlib

import numpy as np


SEM_Z = "4x_sem_a2c_sem_blend_sem_z"
COM_Z = "4x_sem_a2c_sem_blend_com_z"


def projetar_triangulos(posicoes, faces, proj, view, model, largura, altura):
    """Triangula quads como o Vulkan de produção; mantém id de face pai."""
    pos = np.asarray(posicoes, dtype=np.float64)
    faces = np.asarray(faces)
    mats = [np.asarray(x, dtype=np.float64) for x in (proj, view, model)]
    if (
        pos.ndim != 2 or pos.shape[1] != 3
        or faces.ndim != 2 or faces.shape[1] not in (3, 4)
        or not np.issubdtype(faces.dtype, np.integer)
        or len(pos) == 0 or len(faces) == 0
        or any(m.shape != (4, 4) for m in mats)
        or not np.isfinite(pos).all()
        or not all(np.isfinite(m).all() for m in mats)
        or not (isinstance(largura, int) and largura > 0
                and isinstance(altura, int) and altura > 0)
    ):
        raise ValueError("Posições, faces ou matrizes inválidas para projeção")
    if np.any(faces < 0) or np.any(faces >= len(pos)):
        raise ValueError("Índices de face fora da malha")
    faces = faces.astype(np.int64, copy=False)
    ids = np.arange(len(faces), dtype=np.int64)
    if faces.shape[1] == 4:
        tri = np.concatenate(
            [faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]], axis=0
        )
        origens = np.tile(ids, 2)
    else:
        tri, origens = faces, ids
    validos = (
        (tri[:, 0] != tri[:, 1])
        & (tri[:, 0] != tri[:, 2])
        & (tri[:, 1] != tri[:, 2])
    )
    tri, origens = tri[validos], origens[validos]
    coord = np.column_stack([pos, np.ones(len(pos))])
    clip = coord @ (mats[0] @ mats[1] @ mats[2]).T
    clip3 = clip[tri]
    # Não reproduz clipping por plano frustum; triângulos que cruzam o
    # plano próximo são excluídos explicitamente, sem inferir cobertura.
    clip_valido = np.all(
        np.isfinite(clip3).all(axis=2) & (clip3[:, :, 3] > 1e-8),
        axis=1,
    )
    clip3, origens = clip3[clip_valido], origens[clip_valido]
    if not len(clip3):
        raise ValueError("Nenhum triângulo projetável")
    ndc = clip3[:, :, :3] / clip3[:, :, 3:4]
    xy = np.empty((len(ndc), 3, 2), dtype=np.float64)
    xy[:, :, 0] = (ndc[:, :, 0] + 1.0) * (largura / 2.0)
    xy[:, :, 1] = (1.0 - ndc[:, :, 1]) * (altura / 2.0)
    z = (ndc[:, :, 2] + 1.0) / 2.0  # profundidade GL [0,1]
    p0, p1, p2 = xy[:, 0], xy[:, 1], xy[:, 2]
    den = (
        (p1[:, 1] - p2[:, 1]) * (p0[:, 0] - p2[:, 0])
        + (p2[:, 0] - p1[:, 0]) * (p0[:, 1] - p2[:, 1])
    )
    area_ok = np.abs(den) > 1e-8
    xy, z, origens, den = (
        xy[area_ok], z[area_ok], origens[area_ok], den[area_ok]
    )
    if not len(xy):
        raise ValueError("Apenas triângulos de área projetada zero")
    return {
        "xy": xy, "z": z, "faces": origens, "den": den,
        "limites": np.column_stack((
            xy[:, :, 0].min(axis=1), xy[:, :, 1].min(axis=1),
            xy[:, :, 0].max(axis=1), xy[:, :, 1].max(axis=1),
        )),
        "faces_original": len(faces),
        "triangulos_projetaveis": int(len(xy)),
        "triangulos_descartados_clip_ou_degenerados": int(
            len(tri) - len(xy)
        ),
    }


def incidencias_em_pontos(proj, pontos_yx):
    """Incidência geométrica no centro; agrupa triângulos da mesma quad."""
    pts = np.asarray(pontos_yx)
    if pts.ndim != 2 or pts.shape[1] != 2 or not np.isfinite(pts).all():
        raise ValueError("Pontos devem ter shape [N,2] y,x")
    xy, z, faces, den, bbox = (
        proj[k] for k in ("xy", "z", "faces", "den", "limites")
    )
    medidas = []
    for y, x in pts:
        px, py = float(x) + 0.5, float(y) + 0.5
        candidatos = np.flatnonzero(
            (bbox[:, 0] <= px) & (bbox[:, 2] >= px)
            & (bbox[:, 1] <= py) & (bbox[:, 3] >= py)
        )
        if not len(candidatos):
            medidas.append({"faces": 0, "triangulos": 0,
                            "gap_depth_min": None, "range_depth": None})
            continue
        a, b, c = (xy[candidatos, i] for i in range(3))
        d = den[candidatos]
        w0 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0])
              + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / d
        w1 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0])
              + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / d
        w2 = 1.0 - w0 - w1
        inside = (w0 > 1e-7) & (w1 > 1e-7) & (w2 > 1e-7)
        cands = candidatos[inside]
        if not len(cands):
            medidas.append({"faces": 0, "triangulos": 0,
                            "gap_depth_min": None, "range_depth": None})
            continue
        zi = (w0[inside] * z[cands, 0]
              + w1[inside] * z[cands, 1]
              + w2[inside] * z[cands, 2])
        # Uma quad pode ter duas metades cobrindo uma diagonal; não
        # contar ambas como "duas superfícies independentes".
        par = np.lexsort((zi, faces[cands]))
        pais = faces[cands][par]
        zs = zi[par]
        unicos = np.r_[True, pais[1:] != pais[:-1]]
        zs = np.sort(zs[unicos])
        medidas.append({
            "faces": int(unicos.sum()),
            "triangulos": int(len(cands)),
            "gap_depth_min": (
                float(np.diff(zs).min()) if len(zs) >= 2 else None
            ),
            "range_depth": (
                float(zs[-1] - zs[0]) if len(zs) >= 2 else None
            ),
        })
    return medidas


def _resumir(pontos, medidas):
    face_counts = np.asarray([x["faces"] for x in medidas], dtype=np.int64)
    gaps = np.array([
        x["gap_depth_min"] for x in medidas
        if x["gap_depth_min"] is not None
    ], dtype=np.float64)
    return {
        "pixels": len(medidas),
        "com_pelo_menos_1_face": int(np.count_nonzero(face_counts >= 1)),
        "com_pelo_menos_2_faces": int(np.count_nonzero(face_counts >= 2)),
        "com_pelo_menos_3_faces": int(np.count_nonzero(face_counts >= 3)),
        "max_faces": int(face_counts.max()) if len(face_counts) else 0,
        "media_faces": float(face_counts.mean()) if len(face_counts) else 0.0,
        "mediana_gap_depth_multiface": (
            float(np.median(gaps)) if len(gaps) else None
        ),
        "pixels_gap_depth_ate_1e_menos_4": int(np.count_nonzero(gaps <= 1e-4)),
        "amostras_yx_faces": [
            [int(p[0]), int(p[1]), int(m["faces"])]
            for p, m in zip(pontos, medidas)
        ],
        "nota": (
            "Projeção no centro do pixel; múltiplas faces são candidatos "
            "sem culling, alpha test nem depth test efetivo."
        ),
    }


def auditar_corpo(corpo, camera, rgb_sem_z, rgb_com_z,
                  *, largura=1024, altura=768, tolerancia=8,
                  max_controles=512, tamanho_origem=None):
    """Relaciona máscara RGB observada à projeção de faces da mesma malha."""
    a, b = np.asarray(rgb_sem_z), np.asarray(rgb_com_z)
    if (
        a.shape != b.shape or a.shape != (altura, largura, 3)
        or a.dtype != np.uint8 or b.dtype != np.uint8
        or not isinstance(tolerancia, int) or tolerancia < 0
        or not isinstance(max_controles, int) or max_controles < 0
    ):
        raise ValueError("Capturas RGB do corpo ou parâmetros inválidos")
    if not getattr(camera, "updated", True):
        camera.updateCamera()
        camera.updated = True
    proj, view = camera.getMatrices(0)
    proj = np.asarray(proj, dtype=np.float64).copy()
    # mh.renderToBuffer altera G.windowWidth/Height para 1024×768 ANTES
    # de glmodule.cameraPosition(). A função WGPU matriz_wgpu corrige
    # o eixo X pelo aspecto do destino. Após a captura, G já retornou
    # às dimensões da janela; reconstruir o aspecto real do FBO.
    aspecto_origem = None
    if tamanho_origem is not None:
        if (
            not isinstance(tamanho_origem, (tuple, list))
            or len(tamanho_origem) != 2
            or any(not isinstance(v, int) or v <= 0 for v in tamanho_origem)
        ):
            raise ValueError("Dimensões originais da janela inválidas")
        ow, oh = tamanho_origem
        aspecto_origem = float(ow) / float(oh)
        proj[0, :] *= aspecto_origem / (float(largura) / float(altura))
    model = camera.getModelMatrix(corpo)
    pos = np.asarray(corpo.verts)
    faces = np.asarray(corpo.primitives)
    geom = projetar_triangulos(
        pos, faces, proj, view, model, largura, altura
    )
    mudanca = np.any(
        np.abs(a.astype(np.int16) - b.astype(np.int16)) > tolerancia,
        axis=2
    )
    alterados = np.argwhere(mudanca)
    fundo = a[0, 0].astype(np.int16)
    silhueta = np.any(
        np.abs(a.astype(np.int16) - fundo) > 10, axis=2
    )
    # Amostra determinística da silhueta inalterada, distante 1 pixel
    # de fundo. Comparação observacional; não pareamento por anatomia.
    interior = silhueta.copy()
    interior[1:-1, 1:-1] = np.logical_and.reduce([
        silhueta[1+dy:altura-1+dy, 1+dx:largura-1+dx]
        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
    ])
    interior[[0, -1], :] = False
    interior[:, [0, -1]] = False
    nao_alterados = np.argwhere(interior & ~mudanca)
    if len(nao_alterados) > max_controles:
        indices = np.linspace(
            0, len(nao_alterados)-1, max_controles, dtype=np.int64
        )
        nao_alterados = nao_alterados[indices]
    med_a = incidencias_em_pontos(geom, alterados)
    med_b = incidencias_em_pontos(geom, nao_alterados)
    return {
        "tipo": "PROJECAO_CANDIDATOS_Z_MALHA_REAL",
        "estado": "PROJECAO_CPU_DIAGNOSTICA_NAO_GPU",
        "nao_homologado": True,
        "dimensoes": [largura, altura],
        "tolerancia_rgb": tolerancia,
        "tamanho_janela_origem": (
            list(tamanho_origem) if tamanho_origem is not None else None
        ),
        "ajuste_aspecto_fbo": (
            aspecto_origem / (float(largura) / float(altura))
            if aspecto_origem is not None else 1.0
        ),
        "sha256_rgb_sem_z": hashlib.sha256(
            np.ascontiguousarray(a).tobytes()
        ).hexdigest(),
        "sha256_rgb_com_z": hashlib.sha256(
            np.ascontiguousarray(b).tobytes()
        ).hexdigest(),
        "sha256_verts": hashlib.sha256(
            np.ascontiguousarray(pos, dtype="<f4").tobytes()
        ).hexdigest(),
        "sha256_faces": hashlib.sha256(
            np.ascontiguousarray(faces, dtype="<u4").tobytes()
        ).hexdigest(),
        "sha256_mvp_float64": hashlib.sha256(
            np.ascontiguousarray(
                np.asarray(proj) @ np.asarray(view) @ np.asarray(model),
                dtype="<f8",
            ).tobytes()
        ).hexdigest(),
        "quantidade_faces": geom["faces_original"],
        "triangulos_projetaveis": geom["triangulos_projetaveis"],
        "triangulos_descartados": geom[
            "triangulos_descartados_clip_ou_degenerados"
        ],
        "pixels_alterados": _resumir(alterados, med_a),
        "controle_silhueta_inalterada": _resumir(nao_alterados, med_b),
        "limites": (
            "Triângulos candidatos no centro do pixel, não o número de "
            "fragmentos reais. Não aplica clipping, culling, alpha test, "
            "depth test GPU nem MSAA por amostra. Sem cobertura projetada "
            "suficiente no mapa, não inferir auto-sobreposição."
        ),
    }
