"""Compara canal A REAL de mh.renderAlphaMask, não alfa inventado de RGB."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def ler_png_mascara(path, manifesto):
    path = Path(path)
    with Image.open(path) as imagem:
        if imagem.format != "PNG" or imagem.mode != "RGBA":
            raise ValueError(f"Esperado PNG RGBA: {path}, mode={imagem.mode}")
        pixels = np.asarray(imagem, dtype=np.uint8).copy()
    if pixels.shape != (768, 1024, 4):
        raise ValueError(f"Dimensões não são 1024x768 RGBA: {pixels.shape}")
    if np.any(pixels[:, :, :3] != 0):
        raise ValueError("RGB do PNG máscara deve ser zero; o dado está em A")
    alpha = np.ascontiguousarray(pixels[:, :, 3])
    if not np.any(alpha == 0) or not np.any(alpha > 0):
        raise ValueError("Máscara toda vazia ou toda opaca")
    esperado = manifesto.get("mascara_alfa") or {}
    if esperado.get("origem") != "mh.renderAlphaMask":
        raise ValueError("Origem do alfa não está comprovada pela API")
    if esperado.get("sha256_alfa") != hashlib.sha256(alpha.tobytes()).hexdigest():
        raise ValueError("Hash alpha PNG difere do capturado pela API")
    if esperado.get("sha256_png_rgba") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Checksum do PNG não coincide com manifesto")
    return alpha


def metricas_alfa(a, b, *, tolerancia=8, limiar_iou=0.995, fracao_maxima=0.005):
    a, b = np.asarray(a), np.asarray(b)
    if (a.shape != (768, 1024) or b.shape != a.shape
            or a.dtype != np.uint8 or b.dtype != np.uint8):
        raise ValueError("Máscaras alpha devem ser uint8 768x1024")
    diferenca = np.abs(a.astype(np.int16) - b.astype(np.int16))
    cobertura_a, cobertura_b = a > 0, b > 0
    uniao = int(np.count_nonzero(cobertura_a | cobertura_b))
    intersecao = int(np.count_nonzero(cobertura_a & cobertura_b))
    if uniao == 0:
        raise ValueError("IoU não é mensurável para duas máscaras vazias")
    count = int(np.count_nonzero(diferenca > tolerancia))
    iou = intersecao / uniao
    fracao = count / a.size
    return {
        "pixels_total": int(a.size),
        "pixels_alfa_fora_tolerancia_8": count,
        "fracao_alfa_fora_tolerancia_8": fracao,
        "erro_medio_absoluto_alfa": float(diferenca.mean()),
        "erro_maximo_alfa": int(diferenca.max()),
        "intersecao_pixels_cobertos": intersecao,
        "uniao_pixels_cobertos": uniao,
        "iou_cobertura_alfa_real": iou,
        "pixels_cobertos_opengl": int(cobertura_a.sum()),
        "pixels_cobertos_vulkan": int(cobertura_b.sum()),
        "pixels_alfa_parciais_opengl": int(np.count_nonzero((a > 0) & (a < 255))),
        "pixels_alfa_parciais_vulkan": int(np.count_nonzero((b > 0) & (b < 255))),
        "limiares_mascara_propostos_atendidos": bool(
            iou >= limiar_iou and fracao <= fracao_maxima
        ),
    }


def avaliar(ref_png, vk_png, ref_meta, vk_meta, resultado_json, diff_png=None):
    r = json.loads(Path(ref_meta).read_text(encoding="utf-8"))
    v = json.loads(Path(vk_meta).read_text(encoding="utf-8"))
    if r.get("estado") != "CAPTURADO" or v.get("estado") != "OBSERVADO":
        raise ValueError("Ambas as capturas Phong devem estar concluídas")
    if (r.get("captura_mascara_api") is not True
            or v.get("captura_mascara_api") is not True):
        raise ValueError("Falta chamada real a mh.renderAlphaMask")
    alpha_ref = ler_png_mascara(ref_png, r)
    alpha_vk = ler_png_mascara(vk_png, v)
    metricas = metricas_alfa(alpha_ref, alpha_vk)
    registro = {
        "tipo": "PARIDADE_MASCARA_ALFA_API_PHONG",
        "origem": "mh.renderAlphaMask nos dois processos, saída PNG RGBA",
        "mascara_alfa_real_avaliada": True,
        "limiares_propostos_nao_aprovados_pelo_criador": True,
        "paridade_visual_completa_homologada": False,
        "metricas_alfa": metricas,
        "nota": (
            "Mede saída da API renderAlphaMask. Não prova blending nem "
            "alfa de todos os shaders, materiais ou passes."
        ),
    }
    destino = Path(resultado_json)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if diff_png is not None:
        diferenca = np.abs(
            alpha_ref.astype(np.int16) - alpha_vk.astype(np.int16)
        ).astype(np.uint8)
        out = Path(diff_png)
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(diferenca).save(out)
    print(json.dumps(registro, indent=2, ensure_ascii=False), flush=True)
    return registro


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--manifesto-opengl", type=Path, required=True)
    parser.add_argument("--manifesto-vulkan", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--diff", type=Path)
    args = parser.parse_args()
    avaliar(args.opengl, args.vulkan, args.manifesto_opengl,
            args.manifesto_vulkan, args.json, args.diff)


if __name__ == "__main__":
    main()
