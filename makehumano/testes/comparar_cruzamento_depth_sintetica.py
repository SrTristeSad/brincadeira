"""Compara profundidade variável de duas faces no OpenGL e Vulkan.

Audita 9 PNGs RGB8 reais por backend, estados e probes interiores.
Separação espacial: faixa onde o depth cruza, interior distante dela
e borda/exterior. Não infere posições individuais das 4 amostras.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from contrato_cruzamento_depth_sintetica import (
    CASOS_CRUZAMENTO, PROBES_YX, classe_esperada, classificar_pixel,
    passos, regioes_analiticas, vertices,
)


def auditar_manifesto(doc, backend):
    if not (
        doc.get("backend") == backend
        and doc.get("tipo") == "CRUZAMENTO_DEPTH_MSAA4X"
        and doc.get("nao_homologado") is True
        and set(doc.get("controles", {})) == {
            caso[0] for caso in CASOS_CRUZAMENTO
        }
    ):
        raise ValueError("Manifesto de cruzamento incompleto: " + backend)
    from PIL import Image
    imagens = {}
    for caso in CASOS_CRUZAMENTO:
        nome, a2c, z_write, ordem = caso
        c = doc["controles"][nome]
        if not (
            c.get("nome") == nome
            and c.get("a2c_vermelho") is a2c
            and c.get("escrita_z_vermelho") is z_write
            and c.get("ordem") == ordem
            and c.get("depth_compare") == "less-equal"
            and c.get("amostras") == 4
            and c.get("alfa_vermelho") == (128 if a2c else 255)
            and c.get("blend") is False
            and c.get("vertices_vermelho") == vertices("vermelho")
            and c.get("vertices_azul") == vertices("azul")
            and c.get("rastros") == passos(a2c, z_write, ordem)
            and c.get("probes_yx") == [list(p) for p in PROBES_YX]
        ):
            raise ValueError("Estados do draw cruzado inválidos: " + nome)
        if backend == "OpenGL":
            if not (
                c.get("amostras_fbo_observadas") == 4
                and c.get("formato_depth_fbo") == "depth24"
                and c.get("depth_range") == [0.0, 1.0]
            ):
                raise ValueError("FBO de depth OpenGL não comprovado: " + nome)
        elif not (
            c.get("formato_depth_pipeline") == "depth24plus"
            and c.get("amostras_depth_configuradas") == 4
        ):
            raise ValueError("Pipeline depth Vulkan não comprovado: " + nome)
        png = Path(c["png"])
        raw = png.read_bytes()
        if hashlib.sha256(raw).hexdigest() != c.get("sha256_png"):
            raise ValueError("Hash do PNG cruzado inválido: " + nome)
        with Image.open(png) as im:
            if im.mode != "RGB" or im.size != (64, 64):
                raise ValueError("PNG cruzado RGB8 64x64 inválido: " + nome)
            rgb = np.ascontiguousarray(np.asarray(im))
        if (
            hashlib.sha256(rgb.tobytes()).hexdigest() != c.get("sha256_rgb")
            or np.any(rgb[:, :, 1] != 0)
            or int(np.count_nonzero(rgb[:, :, 0]))
                != c.get("pixels_vermelhos")
            or int(np.count_nonzero(rgb[:, :, 2]))
                != c.get("pixels_azuis")
            or int(np.count_nonzero(
                (rgb[:, :, 0] > 0) & (rgb[:, :, 2] > 0)
            )) != c.get("pixels_mistos")
            or [[int(v) for v in rgb[p]] for p in PROBES_YX]
                != c.get("probes_rgb")
        ):
            raise ValueError("Bytes RGB cruzados não correspondem ao manifesto: " + nome)
        for pos in PROBES_YX:
            observado = classificar_pixel(rgb[pos])
            esperado = classe_esperada(caso, pos)
            if observado != esperado:
                raise ValueError(
                    "Depth/A2C no interior não passou: {} {} {} != {}".format(
                        backend, nome, observado, esperado
                    )
                )
        imagens[nome] = rgb
    a = imagens["on_z_on_vermelho_primeiro"]
    b = imagens["on_z_on_repeticao"]
    if not np.array_equal(a, b):
        raise ValueError("Controle repetido não foi idêntico: " + backend)
    regioes = regioes_analiticas()
    for a2c in ("off", "on"):
        nome_frente = "{}_z_on_vermelho_primeiro".format(a2c)
        nome_atras = "{}_z_on_azul_primeiro".format(a2c)
        delta = np.any(
            imagens[nome_frente] != imagens[nome_atras], axis=2
        )
        if np.any(delta & regioes["interior_fora_faixa"]):
            raise ValueError(
                "Inversão de ordem alterou interior longe do cruzamento: "
                + backend + " " + a2c
            )
    return imagens


def comparar_cenas(gl, vk):
    a = auditar_manifesto(gl, "OpenGL")
    b = auditar_manifesto(vk, "Vulkan")
    regioes = regioes_analiticas()
    dados = {}
    for nome, a2c, grava_z, ordem in CASOS_CRUZAMENTO:
        ia = a[nome].astype(np.int16)
        ib = b[nome].astype(np.int16)
        diferem = np.any(ia != ib, axis=2)
        dados[nome] = {
            "a2c": a2c, "escrita_z": grava_z, "ordem": ordem,
            "pixels_rgb_diferentes": int(diferem.sum()),
            "delta_max_rgb": int(np.abs(ia - ib).max()),
            "pixels_faixa_cruzamento": int(np.count_nonzero(
                diferem & regioes["faixa_cruzamento"]
            )),
            "pixels_interior_fora_faixa": int(np.count_nonzero(
                diferem & regioes["interior_fora_faixa"]
            )),
            "pixels_borda_ou_exterior": int(np.count_nonzero(
                diferem & regioes["borda_ou_exterior"]
            )),
        }
    contrastes = {}
    mascaras_z = {}
    for backend, imagens in (("OpenGL", a), ("Vulkan", b)):
        d = {}
        for a2c in ("off", "on"):
            pre = a2c + "_z_on_vermelho_primeiro"
            off = a2c + "_z_off_vermelho_primeiro"
            invertido = a2c + "_z_on_azul_primeiro"
            diferente_z = np.any(imagens[pre] != imagens[off], axis=2)
            diferente_ordem = np.any(
                imagens[pre] != imagens[invertido], axis=2
            )
            d[a2c] = {
                "pixels_alterados_z_on_vs_off": int(diferente_z.sum()),
                "pixels_alterados_z_no_interior_fora_faixa": int(
                    np.count_nonzero(
                        diferente_z & regioes["interior_fora_faixa"]
                    )
                ),
                "pixels_alterados_ao_inverter_ordem": int(
                    diferente_ordem.sum()
                ),
                "pixels_ordenacao_interior_fora_faixa": int(
                    np.count_nonzero(
                        diferente_ordem & regioes["interior_fora_faixa"]
                    )
                ),
            }
            mascaras_z[(backend, a2c)] = diferente_z
        contrastes[backend] = d
    return {
        "tipo": "CRUZAMENTO_DEPTH_Z_MSAA4X",
        "estado": "MEDIDO_SEM_HOMOLOGACAO",
        "amostras": 4,
        "depth_compare": "less-equal",
        "formato_cor": "rgba8unorm linear",
        "faixa_depth_analitica": 0.030,
        "regioes_pixels": {
            k: int(v.sum()) for k, v in regioes.items()
        },
        "gl_vs_vulkan": dados,
        "efeitos_intrabackend": contrastes,
        "nao_homologado": True,
        "limites": (
            "Duas faces de mesma silhueta, depth variável de vértice a vértice "
            "e zwrite controlado. A faixa é estimada em centros de pixels, "
            "não per-sample. Resultados não demonstram causalidade na malha humana."
        ),
    }, a, b, mascaras_z


def salvar_mapa_categorias(mask_gl, mask_vk, png):
    from PIL import Image
    if (
        mask_gl.shape != (64, 64) or mask_vk.shape != mask_gl.shape
        or mask_gl.dtype != bool or mask_vk.dtype != bool
    ):
        raise ValueError("Máscaras 64x64 booleanas necessárias")
    imagem = np.zeros((64, 64, 3), np.uint8)
    imagem[mask_gl & mask_vk] = (195, 195, 195)
    imagem[mask_gl & ~mask_vk] = (255, 75, 75)
    imagem[mask_vk & ~mask_gl] = (35, 235, 255)
    png = Path(png)
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(imagem).resize(
        (512, 512), Image.Resampling.NEAREST
    ).save(png)
    return {
        "png": str(png),
        "sha256_png": hashlib.sha256(png.read_bytes()).hexdigest(),
        "resolucao_dados": [64, 64],
        "resolucao_visual": [512, 512],
        "legenda": {
            "cinza": "efeito de Z em ambos os backends",
            "vermelho": "efeito somente OpenGL",
            "ciano": "efeito somente Vulkan",
            "preto": "ausente em ambos",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--png-z-off", type=Path, required=True)
    parser.add_argument("--png-z-on", type=Path, required=True)
    args = parser.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    if not (
        gl.get("resultado_a2c") == "EXECUTADO_COM_MSAA_4X"
        and vk.get("suporte_msaa", {}).get("disponivel") is True
    ):
        raise ValueError("Harness não comprovou MSAA4x")
    rel, imagens_gl, imagens_vk, masks = comparar_cenas(
        gl["auditoria_sintetica_cruzamento"],
        vk["auditoria_sintetica_cruzamento"],
    )
    # dois mapas: diferença absoluta entre backends sob Z ON com A2C
    # e efeito da chave Z ON/OFF *dentro* de cada backend.
    g = imagens_gl["on_z_on_vermelho_primeiro"]
    v = imagens_vk["on_z_on_vermelho_primeiro"]
    rel["mapas"] = {
        "diferenca_absoluta_a2c_z_on": salvar_mapa_categorias(
            np.any(g > v, axis=2), np.any(v > g, axis=2), args.png_z_on
        ),
        "efeito_z_on_off_a2c": salvar_mapa_categorias(
            masks[("OpenGL", "on")], masks[("Vulkan", "on")],
            args.png_z_off,
        ),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(rel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CRUZAMENTO_DEPTH " + json.dumps({
        "gl_vs_vulkan": rel["gl_vs_vulkan"],
        "efeitos_intrabackend": rel["efeitos_intrabackend"],
        "regioes_pixels": rel["regioes_pixels"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
