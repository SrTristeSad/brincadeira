"""Compare real GPU fullscreen A2C probes without assuming sample locations.

RGB must come from verifiable PNG files, not only JSON claims. White
full-screen or diagonal subpixel triangle over black, rgba8unorm LINEAR,
MSAA 4x, no blending/depth/Phong.
Resolved color alone does not reveal individual subpixel sample masks.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from auditar_cobertura_a2c_sintetica import (
    CASOS, geometria_do_caso, registrar_rgb, vertices_do_caso,
)


def verificar_manifesto(doc, backend):
    if (doc.get("backend") != backend or
            doc.get("tipo") != "A2C_SINTETICO_UMA_SUPERFICIE" or
            doc.get("nao_homologado") is not True):
        raise ValueError("Manifesto sintético inválido " + backend)
    controles = doc.get("controles", {})
    if set(controles) != {c[0] for c in CASOS}:
        raise ValueError("Faltam controles GPU sintéticos: " + backend)
    from PIL import Image
    imagens = {}
    for nome, amostras, a2c, alfa in CASOS:
        c = controles[nome]
        if not (
            c.get("alfa_u8") == alfa
            and c.get("amostras") == amostras
            and c.get("a2c_ativo") is a2c
            and c.get("blend_ativo") is False
            and c.get("profundidade_ativa") is False
            and c.get("geometria") == geometria_do_caso(nome)
            and c.get("vertices_ndc") == [
                list(v) for v in vertices_do_caso(nome)
            ]
        ):
            raise ValueError("Estados sintéticos GPU inesperados: " + backend + " " + nome)
        if backend == "OpenGL" and c.get("amostras_fbo_observadas") != (
            4 if amostras == 4 else 0
        ):
            raise ValueError("FBO OpenGL não comprovou MSAA solicitado")
        arquivo = Path(c["png"])
        dados = arquivo.read_bytes()
        if hashlib.sha256(dados).hexdigest() != c.get("sha256_png"):
            raise ValueError("Hash PNG de A2C sintético incorreto: " + nome)
        with Image.open(arquivo) as im:
            if im.mode != "RGB" or im.size != (64, 64):
                raise ValueError("PNG sintético não é RGB8 64x64")
            rgb = np.ascontiguousarray(np.asarray(im))
        metrica = registrar_rgb(rgb)
        if not all(metrica[chave] == c.get(chave) for chave in (
            "sha256_rgb", "histograma_r", "media_r", "pixels"
        )):
            raise ValueError("Histograma/bytes sintéticos não batem com o manifesto: " + nome)
        if nome in ("1x_a128_a2c_off", "4x_a128_a2c_off", "4x_a255_a2c_on"):
            if not np.all(rgb == 255):
                raise ValueError("Controle branco integral incorreto: " + nome)
        if nome == "4x_a000_a2c_on" and not np.all(rgb == 0):
            raise ValueError("A2C alpha zero deveria cobrir zero pixels")
        if nome in ("aresta_1x_a255_a2c_off", "aresta_4x_a255_a2c_off"):
            if not np.any(rgb == 0) or not np.any(rgb == 255):
                raise ValueError("Aresta sintética sem fundo preto/interior branco")
        if nome == "aresta_4x_a255_a2c_off":
            if not np.any((rgb[:, :, 0] > 0) & (rgb[:, :, 0] < 255)):
                raise ValueError("MSAA 4× sintético não produziu cobertura parcial de borda")
        imagens[nome] = rgb
    for a in (64, 128, 192):
        nome = f"4x_a{a:03d}_a2c_on"
        if np.array_equal(imagens[nome], imagens["4x_a128_a2c_off"]):
            raise ValueError("Driver não alterou cobertura A2C com alfa parcial")
    for nome in ("aresta_4x_a128_a2c_off", "aresta_4x_a255_a2c_on"):
        if not np.array_equal(
            imagens[nome], imagens["aresta_4x_a255_a2c_off"]
        ):
            raise ValueError("Aresta: alfa não poderia mudar RGB sem A2C parcial")
    return imagens


def comparar_sintetico(gl, vk):
    imagens_gl = verificar_manifesto(gl, "OpenGL")
    imagens_vk = verificar_manifesto(vk, "Vulkan")
    dados = {}
    # Borda geométrica é definida pela cobertura PARCIAL em alpha255 com
    # A2C desligado, não pela cor absoluta GL/Vulkan de uma cena Phong.
    borda_gl = imagens_gl["aresta_4x_a255_a2c_off"][:, :, 0]
    borda_vk = imagens_vk["aresta_4x_a255_a2c_off"][:, :, 0]
    borda_uniao = (
        ((borda_gl > 0) & (borda_gl < 255))
        | ((borda_vk > 0) & (borda_vk < 255))
    )
    for nome, amostras, a2c, alfa in CASOS:
        a = imagens_gl[nome].astype(np.int16)
        b = imagens_vk[nome].astype(np.int16)
        delta = np.abs(a - b)
        diferentes = np.any(delta != 0, axis=2)
        dados[nome] = {
            "alfa": alfa, "amostras": amostras, "a2c": a2c,
            "geometria": geometria_do_caso(nome),
            "media_cobertura_gl": gl["controles"][nome]["media_r"] / 255,
            "media_cobertura_vk": vk["controles"][nome]["media_r"] / 255,
            "pixels_rgb_distintos": int(np.count_nonzero(diferentes)),
            "max_diferenca_rgb": int(delta.max()),
            "pixels_diferentes_na_borda_subpixel": int(
                np.count_nonzero(diferentes & borda_uniao)
            ) if nome.startswith("aresta_") else None,
            "pixels_diferentes_fora_da_borda_subpixel": int(
                np.count_nonzero(diferentes & ~borda_uniao)
            ) if nome.startswith("aresta_") else None,
            "histograma_gl": gl["controles"][nome]["histograma_r"],
            "histograma_vk": vk["controles"][nome]["histograma_r"],
        }
    # Como muda A2C na MESMA geometria: não inferimos amostras
    # individuais a partir da diferença de imagens resolvidas.
    mascaras = {}
    for backend, imagens in (("gl", imagens_gl), ("vk", imagens_vk)):
        a = imagens["aresta_4x_a128_a2c_off"].astype(np.int16)
        b = imagens["aresta_4x_a128_a2c_on"].astype(np.int16)
        mascaras[backend] = np.any(np.abs(b - a) > 8, axis=2)
    inter = int(np.count_nonzero(mascaras["gl"] & mascaras["vk"]))
    uniao = int(np.count_nonzero(mascaras["gl"] | mascaras["vk"]))
    # Separa o desacordo que já ocorre com raster MSAA puro daquele
    # medido com A2C. É comparação de SUPORTE, não decomposição causal
    # das cores (a mesma amostra pode mudar de intensidade).
    diferente_msaa = np.any(
        imagens_gl["aresta_4x_a255_a2c_off"] !=
        imagens_vk["aresta_4x_a255_a2c_off"], axis=2,
    )
    diferente_a2c = np.any(
        imagens_gl["aresta_4x_a128_a2c_on"] !=
        imagens_vk["aresta_4x_a128_a2c_on"], axis=2,
    )
    analise_aresta = {
        "diferencas_msaa_puro_vs_a2c": {
            "pixels_msaa_puro": int(diferente_msaa.sum()),
            "pixels_com_a2c_alfa128": int(diferente_a2c.sum()),
            "pixels_em_ambos": int(np.count_nonzero(
                diferente_msaa & diferente_a2c
            )),
            "pixels_somente_no_controle_msaa": int(np.count_nonzero(
                diferente_msaa & ~diferente_a2c
            )),
            "pixels_somente_ao_ativar_a2c": int(np.count_nonzero(
                diferente_a2c & ~diferente_msaa
            )),
            "ressalva": (
                "As máscaras diferentes são de RGB resolvido por pixel, "
                "não representam sample mask individual nem isolam "
                "causalmente a implementação A2C."
            ),
        },
        "pixels_borda_parcial_gl": int(np.count_nonzero(
            (borda_gl > 0) & (borda_gl < 255)
        )),
        "pixels_borda_parcial_vk": int(np.count_nonzero(
            (borda_vk > 0) & (borda_vk < 255)
        )),
        "pixels_uniao_bordas": int(np.count_nonzero(borda_uniao)),
        "pixels_efeito_a2c_128_gl": int(mascaras["gl"].sum()),
        "pixels_efeito_a2c_128_vk": int(mascaras["vk"].sum()),
        "pixels_intersecao_efeito_a2c": inter,
        "pixels_uniao_efeito_a2c": uniao,
        "iou_efeito_a2c": float(inter / uniao) if uniao else 1.0,
        "nota": (
            "Borda subpixel: cobertura parcial 0<R<255 em alpha255 A2C OFF. "
            "Suporte RGB de A2C usa delta máximo >8 entre OFF/ON alpha128. "
            "Não representa sample mask nem posições de amostra."
        ),
    }
    return {
        "tipo": "COMPARACAO_GPU_SINTETICA_A2C_4X",
        "estado": "MEDIDO_SEM_HOMOLOGACAO",
        "amostras_reais": 4,
        "dimensoes": [64, 64],
        "fundo": "preto linear rgba8unorm",
        "fragmento": "RGB branco, alfa constante por controle",
        "profundidade": "ausente",
        "blending": "desligado",
        "textura": "ausente",
        "iluminacao": "ausente",
        "resultados": dados,
        "analise_aresta": analise_aresta,
        "nao_homologado": True,
        "ressalva": (
            "Cores resolvidas pelo MSAA podem variar por posições de amostra "
            "e implementação de A2C. Histograma não reconstrói sample mask; "
            "igualdade sintética não comprova paridade do corpo 3D."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    args = p.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    if (gl.get("resultado_a2c") != "EXECUTADO_COM_MSAA_4X"
            or vk.get("suporte_msaa", {}).get("disponivel") is not True):
        raise ValueError("MSAA4x não foi confirmado nos harnesses do corpo")
    resultado = comparar_sintetico(
        gl["auditoria_sintetica_a2c"], vk["auditoria_sintetica_a2c"]
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "tipo": resultado["tipo"],
        "resultados": resultado["resultados"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
