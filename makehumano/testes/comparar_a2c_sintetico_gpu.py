"""Compare real GPU fullscreen A2C probes without assuming sample locations.

RGB must come from verifiable PNG files, not only JSON claims. White solid
triangle over black, rgba8unorm LINEAR, MSAA 4x, no blending/depth/Phong.
Resolved color alone does not reveal individual subpixel sample masks.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from auditar_cobertura_a2c_sintetica import CASOS, registrar_rgb


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
        imagens[nome] = rgb
    for a in (64, 128, 192):
        nome = f"4x_a{a:03d}_a2c_on"
        if np.array_equal(imagens[nome], imagens["4x_a128_a2c_off"]):
            raise ValueError("Driver não alterou cobertura A2C com alfa parcial")
    return imagens


def comparar_sintetico(gl, vk):
    imagens_gl = verificar_manifesto(gl, "OpenGL")
    imagens_vk = verificar_manifesto(vk, "Vulkan")
    dados = {}
    for nome, amostras, a2c, alfa in CASOS:
        a = imagens_gl[nome].astype(np.int16)
        b = imagens_vk[nome].astype(np.int16)
        delta = np.abs(a - b)
        diferentes = np.any(delta != 0, axis=2)
        dados[nome] = {
            "alfa": alfa, "amostras": amostras, "a2c": a2c,
            "media_cobertura_gl": gl["controles"][nome]["media_r"] / 255,
            "media_cobertura_vk": vk["controles"][nome]["media_r"] / 255,
            "pixels_rgb_distintos": int(np.count_nonzero(diferentes)),
            "max_diferenca_rgb": int(delta.max()),
            "histograma_gl": gl["controles"][nome]["histograma_r"],
            "histograma_vk": vk["controles"][nome]["histograma_r"],
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
