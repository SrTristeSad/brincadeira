"""Compara canal A REAL de mh.renderAlphaMask, não alfa inventado de RGB."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def ler_png_mascara(path, manifesto, *, campo="mascara_alfa"):
    # Pillow só é exigido ao abrir PNGs; a suíte CPU importa metricas_alfa
    # sem precisar desta dependência de análise de artefatos.
    from PIL import Image
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
    esperado = manifesto.get(campo) or {}
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


def avaliar(ref_png, vk_png, ref_meta, vk_meta, resultado_json, diff_png=None,
            ref_parcial=None, vk_parcial=None, diff_parcial=None):
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
    parcial = None
    if (ref_parcial is None) != (vk_parcial is None):
        raise ValueError("Máscaras parciais exigem OpenGL e Vulkan em par")
    if ref_parcial is not None:
        if not (r.get("captura_mascara_parcial_api") is True
                and v.get("captura_mascara_parcial_api") is True):
            raise ValueError("Os dois manifestos precisam comprovar controle parcial")
        controle_ref = r.get("controle_alfa_parcial", {})
        controle_vk = v.get("controle_alfa_parcial", {})
        tex_r, tex_v = controle_ref.get("textura"), controle_vk.get("textura")
        if (not isinstance(tex_r, dict) or tex_r != tex_v
                or tex_r.get("alfa_textura") != 128
                or tex_r.get("shape") != [32, 32, 4]
                or tex_r.get("origem") != "png_temporario_de_harness"):
            raise ValueError("Textura de teste não é idêntica nos dois backends")
        for controle in (controle_ref, controle_vk):
            m = controle.get("material", {})
            if (m.get("opacity") != 1.0
                    or m.get("transparent") is not True
                    or m.get("alphaToCoverage") is not False
                    or m.get("define_diffuse_ativo") is not True
                    or m.get("mapas", {}).get("diffuseTexture", {}).get("origem")
                       != "arquivo"
                    or m.get("mapas", {}).get("diffuseTexture", {}).get("sha256")
                       != tex_r.get("sha256_png")):
                raise ValueError("Material do controle parcial não preserva parâmetros pareados")
        a = ler_png_mascara(ref_parcial, r, campo="mascara_alfa_parcial")
        b = ler_png_mascara(vk_parcial, v, campo="mascara_alfa_parcial")
        met = metricas_alfa(a, b)
        parcial_ref = (a > 0) & (a < 255)
        parcial_vk = (b > 0) & (b < 255)
        ambos_observaram = bool(np.any(parcial_ref) and np.any(parcial_vk))
        met["alfa_parcial_observado_nos_dois"] = ambos_observaram
        met["limiares_parciais_propostos_atendidos"] = bool(
            ambos_observaram and met["limiares_mascara_propostos_atendidos"]
        )
        inter = (a > 0) & (b > 0)
        met["alfa_medio_opengl_na_intersecao"] = float(a[inter].mean()) if inter.any() else None
        met["alfa_medio_vulkan_na_intersecao"] = float(b[inter].mean()) if inter.any() else None
        parcial = {
            "configuracao": "RGBA 32x32 xadrez, A=128, DIFFUSE ativo, opacity=1, A2C desligado",
            "sha256_textura_rgba": tex_r["sha256_rgba"],
            "controlado_apenas_no_harness": True,
            "metricas_alfa": met,
            "estado": ("ALFA_PARCIAL_OBSERVADO" if ambos_observaram
                       else "NAO_OBSERVOU_ALFA_PARCIAL_EM_AMBOS"),
            "nota": ("GL usa passe aditivo e Vulkan usa blend alpha habitual; "
                     "igualdade numérica não deve ser presumida."),
        }
        if diff_parcial is not None:
            from PIL import Image
            diferenca_p = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)
            out_p = Path(diff_parcial)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(diferenca_p).save(out_p)
    registro = {
        "tipo": "PARIDADE_MASCARA_ALFA_API_PHONG",
        "origem": "mh.renderAlphaMask nos dois processos, saída PNG RGBA",
        "mascara_alfa_real_avaliada": True,
        "limiares_propostos_nao_aprovados_pelo_criador": True,
        "paridade_visual_completa_homologada": False,
        "metricas_alfa": metricas,
        "controle_textura_alfa_parcial": parcial,
        "nota": (
            "Mede saída da API renderAlphaMask. Não prova blending nem "
            "alfa de todos os shaders, materiais ou passes."
        ),
    }
    destino = Path(resultado_json)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if diff_png is not None:
        from PIL import Image
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
    parser.add_argument("--opengl-parcial", type=Path)
    parser.add_argument("--vulkan-parcial", type=Path)
    parser.add_argument("--diff-parcial", type=Path)
    args = parser.parse_args()
    avaliar(args.opengl, args.vulkan, args.manifesto_opengl,
            args.manifesto_vulkan, args.json, args.diff,
            args.opengl_parcial, args.vulkan_parcial, args.diff_parcial)


if __name__ == "__main__":
    main()
