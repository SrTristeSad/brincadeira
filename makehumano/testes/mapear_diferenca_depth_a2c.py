"""Diagnóstico reproduzível do efeito isolado de escrita Z, por backend.

Não compara diretamente RGB OpenGL com RGB Vulkan. Os PNGs são auditados
contra os manifests por hashes de arquivo e bytes RGB antes de análise.
Sem correção de renderer e sem critério de homologação.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from mapear_efeito_a2c_rgb import (
    erodir_mascara, ler_captura, mascara_efeito,
)


SEM_Z = "4x_sem_a2c_sem_blend_sem_z"
COM_Z = "4x_sem_a2c_sem_blend_com_z"


def componentes_8_conexos(mask):
    """Componentes 8-conexos de pixels divergentes, sem SciPy."""
    mascara = np.asarray(mask)
    if mascara.ndim != 2 or mascara.dtype != bool:
        raise ValueError("Máscara booleana HxW necessária")
    altura, largura = mascara.shape
    visitado = np.zeros_like(mascara)
    componentes = []
    for sy, sx in np.argwhere(mascara):
        sy, sx = int(sy), int(sx)
        if visitado[sy, sx]:
            continue
        visitado[sy, sx] = True
        pilha = [(sy, sx)]
        quantidade = 0
        x0 = x1 = sx
        y0 = y1 = sy
        while pilha:
            y, x = pilha.pop()
            quantidade += 1
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < altura and 0 <= nx < largura
                            and mascara[ny, nx] and not visitado[ny, nx]):
                        visitado[ny, nx] = True
                        pilha.append((ny, nx))
        componentes.append({
            "pixels": quantidade,
            "bbox_xyxy": [x0, y0, x1, y1],
        })
    componentes.sort(
        key=lambda item: (-item["pixels"], item["bbox_xyxy"])
    )
    return componentes


def analisar_profundidade(sem_z, com_z, *, tolerancia=8,
                          limiar_fundo=10, erosao_pixels=1):
    a, b = np.asarray(sem_z), np.asarray(com_z)
    mudanca = mascara_efeito(a, b, tolerancia=tolerancia)
    mudanca_absoluta = mascara_efeito(a, b, tolerancia=0)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    fundo = a[0, 0].astype(np.int16)
    silhueta_estimada = np.any(
        np.abs(a.astype(np.int16) - fundo) > limiar_fundo,
        axis=2,
    )
    interior = erodir_mascara(silhueta_estimada, pixels=erosao_pixels)
    total = int(mudanca.sum())
    componentes = componentes_8_conexos(mudanca)
    ys, xs = np.nonzero(mudanca)
    altura, largura = mudanca.shape
    metrica = {
        "pixels_alterados_gt_tolerancia": total,
        "pixels_alterados_qualquer_delta": int(mudanca_absoluta.sum()),
        "dimensoes": [largura, altura],
        "tolerancia_rgb": tolerancia,
        "fundo_rgb": [int(v) for v in a[0, 0]],
        "max_delta_canal_rgb": int(delta.max()),
        "bbox_total_xyxy": [
            int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        ] if total else None,
        "pixels_no_interior_estimado": int(np.count_nonzero(mudanca & interior)),
        "pixels_na_faixa_de_borda_ou_exterior": int(
            np.count_nonzero(mudanca & ~interior)
        ),
        "pixels_fora_da_silhueta_estimada": int(
            np.count_nonzero(mudanca & ~silhueta_estimada)
        ),
        "interior_estimado_erosao_px": erosao_pixels,
        "limiar_silhueta_ao_fundo_rgb": limiar_fundo,
        "quantidade_componentes_8_conexos": len(componentes),
        "componentes_maiores": componentes[:20],
        "fracao_4_maiores_componentes": (
            sum(c["pixels"] for c in componentes[:4]) / total if total else 0.0
        ),
        "nota": (
            "A silhueta é inferida da cor RGB do pixel de fundo. Não prova "
            "overdraw, ordenação, visibilidade de triângulos ou paridade Z."
        ),
    }
    return metrica, mudanca


def checar_estados(manifesto, backend):
    for nome, z in ((SEM_Z, False), (COM_Z, True)):
        c = manifesto["controles"][nome]
        if not (
            c["captura_rgb"] is True
            and c["amostras"] == 4
            and c["controle_blend_desligado"] is True
            and c["blend_habilitado_observado"] is False
            and c["escrita_z_observada"] is z
            and c["pipeline_a2c_observado"] is False
            and c["nTransparentPrimitives"] > 0
        ):
            raise ValueError("Estado incorreto no ensaio Z: " + backend + " " + nome)
        if backend == "OpenGL":
            if c["amostras_fbo_observadas"] != 4 or not c["rastros_gl"]["draw_states"]:
                raise ValueError("FBO/draw GL não confirmado")
            if not all(x == {
                "blend": False, "escrita_z": z, "a2c": False
            } for x in c["rastros_gl"]["draw_states"]):
                raise ValueError("GL apresentou estados divergentes no draw")
        elif backend == "Vulkan":
            if (c["pipeline_chave_cache_confirmada"] is not True
                    or not c["rastros_pipeline_corpo"]):
                raise ValueError("Pipeline Vulkan não comprovado")
            if not all(
                x["blend_habilitado_previsto"] is False
                and x["escrita_z_prevista"] is z
                and x["a2c_calculado"] is False
                for x in c["rastros_pipeline_corpo"]
            ):
                raise ValueError("Variante Vulkan divergente")


def auditar_manifestos(gl, vk):
    if gl.get("estado") != "CAPTURADO" or vk.get("estado") != "OBSERVADO":
        raise ValueError("Captura de referência incompleta")
    if gl.get("dimensoes_imagem") != vk.get("dimensoes_imagem") != [1024, 768]:
        raise ValueError("Dimensões incompatíveis")
    for backend, manifesto in (("OpenGL", gl), ("Vulkan", vk)):
        checar_estados(manifesto, backend)
    if gl["textura_controle"]["sha256_png"] != vk["textura_controle"]["sha256_png"]:
        raise ValueError("Texturas diferentes entre GL e Vulkan")


def gerar_overlay(rgb, mask):
    imagem = np.asarray(rgb).copy()
    if imagem.dtype != np.uint8 or imagem.ndim != 3 or imagem.shape[2] != 3:
        raise ValueError("Imagem base RGB uint8 necessária")
    if mask.shape != imagem.shape[:2] or mask.dtype != bool:
        raise ValueError("Máscara incompatible com o RGB")
    imagem[mask] = [255, 40, 40]
    return imagem


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--png-gl", type=Path, required=True)
    p.add_argument("--png-vk", type=Path, required=True)
    args = p.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    auditar_manifestos(gl, vk)
    from PIL import Image
    doc = {
        "tipo": "MAPA_DE_PROFUNDIDADE_ISOLADA_4X",
        "nao_homologado": True,
        "manifestos": {},
    }
    for nome, m, caminho in (
        ("opengl", gl, args.png_gl), ("vulkan", vk, args.png_vk)
    ):
        anterior = ler_captura(m["controles"][SEM_Z])
        posterior = ler_captura(m["controles"][COM_Z])
        metrica, mask = analisar_profundidade(anterior, posterior)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(gerar_overlay(anterior, mask), mode="RGB").save(caminho)
        doc["manifestos"][nome] = {
            **metrica,
            "overlay_png": str(caminho),
            "sha256_png": hashlib.sha256(caminho.read_bytes()).hexdigest(),
        }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(doc, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
