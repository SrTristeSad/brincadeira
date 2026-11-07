"""Confere o mapa Z real da GUI contra a geometria projetada registrada.

O mapa não prova overdraw: conta candidatos geométricos no centro do
pixel, antes de culling, alpha test, profundidade e MSAA por amostra.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from auditar_auto_sobreposicao_malha import SEM_Z, COM_Z
from mapear_efeito_a2c_rgb import ler_captura


def auditar_registro(manifesto, backend):
    if manifesto.get("backend") != backend:
        raise ValueError("Backend de auto-sobreposição incorreto")
    reg = manifesto.get("auditoria_auto_sobreposicao_z", {})
    if not (
        reg.get("tipo") == "PROJECAO_CANDIDATOS_Z_MALHA_REAL"
        and reg.get("estado") == "PROJECAO_CPU_DIAGNOSTICA_NAO_GPU"
        and reg.get("nao_homologado") is True
        and reg.get("dimensoes") == [1024, 768]
        and reg.get("tolerancia_rgb") == 8
        and isinstance(reg.get("sha256_verts"), str)
        and len(reg["sha256_verts"]) == 64
        and isinstance(reg.get("sha256_faces"), str)
        and len(reg["sha256_faces"]) == 64
        and isinstance(reg.get("sha256_mvp_float64"), str)
        and len(reg["sha256_mvp_float64"]) == 64
        and reg.get("quantidade_faces", 0) > 0
        and reg.get("triangulos_projetaveis", 0) > 0
    ):
        raise ValueError("Auditoria geométrica incompleta: " + backend)
    controls = manifesto["controles"]
    for chave, prefixo in ((SEM_Z, "sem_z"), (COM_Z, "com_z")):
        controle = controls[chave]
        if not (
            controle.get("captura_rgb") is True
            and controle.get("amostras") == 4
            and controle.get("controle_blend_desligado") is True
            and controle.get("pipeline_a2c_observado") is False
            and controle.get("escrita_z_observada") is (chave == COM_Z)
        ):
            raise ValueError("Estado RGB/Z incompatível: " + backend)
    a, b = (ler_captura(controls[k]) for k in (SEM_Z, COM_Z))
    for name, arr in (("sem_z", a), ("com_z", b)):
        if hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest() != reg[
            "sha256_rgb_" + name
        ]:
            raise ValueError("Hash RGB da projeção diferente do PNG: " + name)
    if a.shape != b.shape or a.shape != (768, 1024, 3):
        raise ValueError("RGB não corresponde ao tamanho da auditoria")
    mudanca = np.any(
        np.abs(a.astype(np.int16) - b.astype(np.int16)) > 8, axis=2
    )
    coords = np.argwhere(mudanca)
    alterados = reg["pixels_alterados"]
    amostras = alterados.get("amostras_yx_faces")
    if (
        alterados.get("pixels") != len(coords)
        or not isinstance(amostras, list)
        or len(amostras) != len(coords)
        or any(
            len(x) != 3 or x[0] != int(p[0]) or x[1] != int(p[1])
            or not isinstance(x[2], int) or x[2] < 0
            for x, p in zip(amostras, coords)
        )
    ):
        raise ValueError("Mapa de pixels alterados não corresponde aos PNGs")
    contagem = np.array([x[2] for x in amostras], dtype=np.int64)
    for n, campo in ((1, "com_pelo_menos_1_face"),
                     (2, "com_pelo_menos_2_faces"),
                     (3, "com_pelo_menos_3_faces")):
        if alterados.get(campo) != int(np.count_nonzero(contagem >= n)):
            raise ValueError("Contagem de candidatos geométricos adulterada")
    controles = reg["controle_silhueta_inalterada"]
    if not (
        isinstance(controles.get("amostras_yx_faces"), list)
        and controles.get("pixels") == len(controles["amostras_yx_faces"])
        and controles["pixels"] <= 512
    ):
        raise ValueError("Amostra de controle geométrico inválida")
    for y, x, faces in controles["amostras_yx_faces"]:
        if (
            not (0 <= y < 768 and 0 <= x < 1024)
            or mudanca[y, x] or not isinstance(faces, int) or faces < 0
        ):
            raise ValueError("Controle geométrico não é pixel inalterado")
    return reg, a, mudanca


def gerar_mapa(reg, origem, mascara, destino):
    """Sobreposição Z: vermelho 2+ faces, amarelo 1, violeta 0."""
    from PIL import Image
    mapa = np.asarray(origem).copy()
    pixels = reg["pixels_alterados"]["amostras_yx_faces"]
    if len(pixels) != int(mascara.sum()):
        raise ValueError("Mapa e lista geométrica de Z não coincidem")
    for y, x, faces in pixels:
        if not mascara[y, x]:
            raise ValueError("Pixel fora da máscara Z validada")
        mapa[y, x] = (
            [255, 48, 48] if faces >= 2
            else [255, 215, 35] if faces == 1
            else [190, 55, 220]
        )
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mapa, mode="RGB").save(destino)
    return {
        "png": str(destino),
        "sha256_png": hashlib.sha256(destino.read_bytes()).hexdigest(),
        "legenda": {
            "vermelho": "pixel Z alterado com 2+ faces projetadas",
            "amarelo": "pixel Z alterado com 1 face projetada",
            "violeta": "pixel Z alterado sem face projetada no centro",
            "demais": "RGB original do corpo no controle Z OFF",
        },
    }


def comparar_analises(gl, vk):
    ag, rgbg, maskg = auditar_registro(gl, "OpenGL")
    av, rgbv, maskv = auditar_registro(vk, "Vulkan")
    return {
        "tipo": "AUTO_SOBREPOSICAO_PROJETADA_Z_GL_VULKAN",
        "estado": "MEDIDO_SEM_HOMOLOGACAO",
        "nao_homologado": True,
        "assinaturas_geometria_iguais": (
            ag["sha256_verts"] == av["sha256_verts"]
            and ag["sha256_faces"] == av["sha256_faces"]
        ),
        "assinatura_mvp_igual": (
            ag["sha256_mvp_float64"] == av["sha256_mvp_float64"]
        ),
        "pixels_z_em_ambos": int(np.count_nonzero(maskg & maskv)),
        "pixels_z_uniao": int(np.count_nonzero(maskg | maskv)),
        "opengl": {
            "faces_malha": ag["quantidade_faces"],
            "triangulos_projetaveis": ag["triangulos_projetaveis"],
            "triangulos_descartados": ag["triangulos_descartados"],
            "alterados": {
                k: v for k, v in ag["pixels_alterados"].items()
                if k != "amostras_yx_faces"
            },
            "controle": {
                k: v for k, v in ag["controle_silhueta_inalterada"].items()
                if k != "amostras_yx_faces"
            },
        },
        "vulkan": {
            "faces_malha": av["quantidade_faces"],
            "triangulos_projetaveis": av["triangulos_projetaveis"],
            "triangulos_descartados": av["triangulos_descartados"],
            "alterados": {
                k: v for k, v in av["pixels_alterados"].items()
                if k != "amostras_yx_faces"
            },
            "controle": {
                k: v for k, v in av["controle_silhueta_inalterada"].items()
                if k != "amostras_yx_faces"
            },
        },
        "limites": (
            "Contagem de faces projetadas é observação da malha, NÃO de "
            "fragmentos realmente desenhados. Pixels de cobertura MSAA "
            "podem divergir do centro; clipping/culling/alpha/depth não são "
            "reproduzidos pelo diagnóstico CPU. Não alterar produção."
        ),
    }, (ag, rgbg, maskg), (av, rgbv, maskv)


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
    rel, (ag, rgbg, maskg), (av, rgbv, maskv) = comparar_analises(gl, vk)
    rel["mapas"] = {
        "opengl": gerar_mapa(ag, rgbg, maskg, args.png_gl),
        "vulkan": gerar_mapa(av, rgbv, maskv, args.png_vk),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(rel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "tipo": rel["tipo"],
        "assinaturas_geometria_iguais": rel["assinaturas_geometria_iguais"],
        "assinatura_mvp_igual": rel["assinatura_mvp_igual"],
        "opengl": rel["opengl"], "vulkan": rel["vulkan"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
