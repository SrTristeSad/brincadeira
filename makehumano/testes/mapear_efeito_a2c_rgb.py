"""Compara LOCALIZAÇÃO do efeito RGB A2C (ON-OFF) em GL e Vulkan.

Usa máscaras de mudança intrabackend, não diffs de cor absoluta GL vs Vulkan.
O mapa e as métricas são diagnósticos, não homologação de paridade visual.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def mascara_efeito(off, on, *, tolerancia=8):
    a = np.asarray(off)
    b = np.asarray(on)
    if a.shape != b.shape or a.ndim != 3 or a.shape[2] != 3:
        raise ValueError("Controles RGB precisam ter dimensões HxWx3 idênticas")
    if a.dtype != np.uint8 or b.dtype != np.uint8:
        raise ValueError("Controles RGB devem ter dtype uint8")
    if not 0 <= tolerancia <= 255:
        raise ValueError("Tolerância RGB inválida")
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return np.any(d > tolerancia, axis=2)


def dilatar_um_pixel(mask):
    m = np.asarray(mask)
    if m.ndim != 2 or m.dtype != bool:
        raise ValueError("Máscara precisa ser booleana e bidimensional")
    h, w = m.shape
    out = np.zeros_like(m)
    pad = np.pad(m, 1, mode="constant", constant_values=False)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    return out


def analisar_efeitos(off_gl, on_gl, off_vk, on_vk, *, tolerancia=8):
    mg = mascara_efeito(off_gl, on_gl, tolerancia=tolerancia)
    mv = mascara_efeito(off_vk, on_vk, tolerancia=tolerancia)
    if mg.shape != mv.shape:
        raise ValueError("Matrizes de GL e Vulkan possuem dimensões diferentes")
    inter = mg & mv
    uniao = mg | mv
    qtd_gl, qtd_vk = int(mg.sum()), int(mv.sum())
    qtd_inter, qtd_uniao = int(inter.sum()), int(uniao.sum())
    viz_gl, viz_vk = dilatar_um_pixel(mg), dilatar_um_pixel(mv)
    d = {
        "tolerancia_rgb": int(tolerancia),
        "dimensoes": [int(mg.shape[1]), int(mg.shape[0])],
        "pixels_efeito_gl": qtd_gl,
        "pixels_efeito_vk": qtd_vk,
        "pixels_intersecao": qtd_inter,
        "pixels_uniao": qtd_uniao,
        "pixels_so_gl": int((mg & ~mv).sum()),
        "pixels_so_vk": int((mv & ~mg).sum()),
        "iou_localizacao_efeito": qtd_inter / qtd_uniao if qtd_uniao else 1.0,
        "fracao_pixels_gl_a_ate_1px_de_vk":
            float((mg & viz_vk).sum()) / qtd_gl if qtd_gl else 1.0,
        "fracao_pixels_vk_a_ate_1px_de_gl":
            float((mv & viz_gl).sum()) / qtd_vk if qtd_vk else 1.0,
        "nao_homologado": True,
    }
    return d, mg, mv


def criar_mapa(mg, mv):
    if mg.shape != mv.shape:
        raise ValueError("Máscaras não alinhadas")
    img = np.zeros((*mg.shape, 3), dtype=np.uint8)
    img[mg & ~mv] = (255, 75, 75)   # somente OpenGL
    img[mv & ~mg] = (35, 185, 240)  # somente Vulkan
    img[mg & mv] = (255, 255, 255)  # interseção
    return img


def ler_captura(controle):
    # Pillow é dependência somente de diagnóstico na CI, não do produto.
    from PIL import Image
    caminho = Path(controle["arquivo_rgb"])
    arquivo = caminho.read_bytes()
    if hashlib.sha256(arquivo).hexdigest() != controle["sha256_png"]:
        raise ValueError("Hash PNG inválido: " + str(caminho))
    with Image.open(caminho) as imagem:
        if imagem.mode != "RGB":
            raise ValueError("PNG da captura não está em RGB")
        rgb = np.ascontiguousarray(np.asarray(imagem))
    if hashlib.sha256(rgb.tobytes()).hexdigest() != controle["sha256_rgb"]:
        raise ValueError("Hash de pixels RGB inválido: " + str(caminho))
    return rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--pareamento", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    args = parser.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    pareado = json.loads(args.pareamento.read_text(encoding="utf-8"))
    doc = {
        "tipo": "MAPA_ESPACIAL_EFEITO_A2C_RGB",
        "nao_homologado": True,
        "base": "diff RGB intrabackend entre 4x OFF e 4x ON",
        "legenda": {"vermelho": "so_gl", "ciano": "so_vulkan",
                    "branco": "ambos", "preto": "nenhum"},
        "estado": "NAO_TESTAVEL_OPENGL_4X",
    }
    if pareado["estado"] == "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS":
        entradas = [
            ler_captura(m["controles"][nome])
            for m in (gl, vk)
            for nome in ("4x_sem_a2c", "4x_com_a2c")
        ]
        metrica, mg, mv = analisar_efeitos(*entradas)
        doc.update(metrica)
        doc["estado"] = "MEDIDO_SEM_HOMOLOGACAO"
        from PIL import Image
        args.png.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(criar_mapa(mg, mv), mode="RGB").save(args.png)
        doc["arquivo_mapa_png"] = str(args.png)
        doc["sha256_mapa_png"] = hashlib.sha256(args.png.read_bytes()).hexdigest()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
