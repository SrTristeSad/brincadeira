"""Audita duas superfícies com Z e A2C usando os PNGs GL/VK reais.

A diferença entre ordem invertida, depth-write OFF e ON é analisada sem
alterar o renderer de produção. Não assume que GL/Vulkan escolham as
mesmas posições subpixel, nem que pixels RGB resolvidos revelem sample mask.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from contrato_sobreposicao_depth_sintetica import (
    CASOS_SOBREPOSICAO, DEPTH_FRENTE, DEPTH_FUNDO,
    resumir_rgb, sequencia_draw, vertices_com_profundidade,
)


def auditar_manifesto(doc, backend):
    if (
        doc.get("backend") != backend
        or doc.get("tipo") != "SOBREPOSICAO_DEPTH_A2C_SINTETICA"
        or doc.get("nao_homologado") is not True
        or set(doc.get("controles", {})) != {x[0] for x in CASOS_SOBREPOSICAO}
    ):
        raise ValueError("Manifesto de sobreposição inválido: " + backend)
    from PIL import Image

    imagens = {}
    for nome, a2c, escreve_z, ordem in CASOS_SOBREPOSICAO:
        c = doc["controles"][nome]
        if not (
            c.get("nome") == nome
            and c.get("amostras") == 4
            and c.get("alfa_frente") == (128 if a2c else 255)
            and c.get("a2c_frente") is a2c
            and c.get("escrita_z_frente") is escreve_z
            and c.get("ordem") == ordem
            and c.get("depth_test") is True
            and c.get("blending") is False
            and c.get("depth_compare") == "less"
            and c.get("depth_fundo") == DEPTH_FUNDO
            and c.get("depth_frente") == DEPTH_FRENTE
            and c.get("vertices_frente") == vertices_com_profundidade("frente")
            and c.get("vertices_fundo") == vertices_com_profundidade("fundo")
            and c.get("rastros_draw") == sequencia_draw(a2c, escreve_z, ordem)
        ):
            raise ValueError("Estados do draw de profundidade inválidos: " + nome)
        if backend == "OpenGL":
            if (
                c.get("amostras_fbo_observadas") != 4
                or c.get("fbo_depth_formato") != "depth24"
            ):
                raise ValueError("FBO OpenGL depth não comprovado")
        else:
            if (
                c.get("formato_depth_pipeline") != "depth24plus"
                or c.get("amostras_depth_configuradas") != 4
            ):
                raise ValueError("Vulkan depth pipeline inválido")
        arquivo = Path(c["png"])
        if hashlib.sha256(arquivo.read_bytes()).hexdigest() != c.get("sha256_png"):
            raise ValueError("Hash PNG depth incorreto: " + nome)
        with Image.open(arquivo) as im:
            if im.mode != "RGB" or im.size != (64, 64):
                raise ValueError("PNG depth não é RGB8 64x64")
            rgb = np.ascontiguousarray(np.asarray(im))
        metrica = resumir_rgb(rgb)
        if not all(metrica[k] == c.get(k) for k in metrica):
            raise ValueError("Manifesto RGB depth incoerente: " + nome)
        imagens[nome] = rgb

    # Contratos físicos do experimento, sem depender da cor das arestas.
    azul = np.array([0, 0, 255], np.uint8)
    for nome in ("a2c_off_z_off", "a2c_on_z_off"):
        if not np.all(imagens[nome] == azul):
            raise ValueError("Sem escrever Z, o fundo deveria cobrir tudo: " + nome)
    if imagens["a2c_off_z_on"][32, 32].tolist() != [255, 0, 0]:
        raise ValueError("Centro vermelho da frente não passou no depth")
    centro_a2c = imagens["a2c_on_z_on"][32, 32]
    if not (0 < int(centro_a2c[0]) < 255 and
            0 < int(centro_a2c[2]) < 255):
        raise ValueError("A2C parcial não preservou mistura red/blue no centro")
    for a, b in (
        ("a2c_off_z_on", "a2c_off_z_on_inverso"),
        ("a2c_on_z_on", "a2c_on_z_on_inverso"),
        ("a2c_on_z_on", "a2c_on_z_on_repeticao"),
    ):
        if not np.array_equal(imagens[a], imagens[b]):
            raise ValueError("Ordem/restauração alterou profundidade: " + a + " " + b)
    return imagens


def comparar_sobreposicao(gl, vk):
    imgs_gl = auditar_manifesto(gl, "OpenGL")
    imgs_vk = auditar_manifesto(vk, "Vulkan")
    bgl = imgs_gl["a2c_off_z_on"][:, :, 0]
    bvk = imgs_vk["a2c_off_z_on"][:, :, 0]
    borda = ((bgl > 0) & (bgl < 255)) | ((bvk > 0) & (bvk < 255))
    resultados = {}
    for nome, a2c, z, ordem in CASOS_SOBREPOSICAO:
        ag = imgs_gl[nome].astype(np.int16)
        av = imgs_vk[nome].astype(np.int16)
        delta = np.abs(ag - av)
        diferentes = np.any(delta != 0, axis=2)
        resultados[nome] = {
            "pixels_rgb_diferentes": int(diferentes.sum()),
            "pixels_divergentes_na_borda_msaa": int(
                np.count_nonzero(diferentes & borda)
            ),
            "pixels_divergentes_fora_borda": int(
                np.count_nonzero(diferentes & ~borda)
            ),
            "max_diferenca_rgb": int(delta.max()),
            "centro_rgb_gl": gl["controles"][nome]["centro_rgb"],
            "centro_rgb_vk": vk["controles"][nome]["centro_rgb"],
            "a2c_frente": a2c,
            "escrita_z_frente": z,
            "ordem": ordem,
        }
    diff_puro = np.any(
        imgs_gl["a2c_off_z_on"] != imgs_vk["a2c_off_z_on"], axis=2
    )
    diff_a2c = np.any(
        imgs_gl["a2c_on_z_on"] != imgs_vk["a2c_on_z_on"], axis=2
    )
    return {
        "tipo": "COMPARACAO_SOBREPOSICAO_DEPTH_A2C",
        "estado": "VERIFICADO_SEM_HOMOLOGACAO",
        "msaa": 4,
        "formato_cor": "rgba8unorm linear",
        "sem_blend": True,
        "frente_z": DEPTH_FRENTE,
        "fundo_z": DEPTH_FUNDO,
        "resultados": resultados,
        "analise": {
            "pixels_borda_geometrica_parcial_uniao": int(borda.sum()),
            "pixels_divergentes_msaa_puro": int(diff_puro.sum()),
            "pixels_divergentes_a2c_alpha128": int(diff_a2c.sum()),
            "pixels_em_ambos": int(np.count_nonzero(diff_puro & diff_a2c)),
            "pixels_so_msaa_puro": int(np.count_nonzero(diff_puro & ~diff_a2c)),
            "pixels_so_a2c": int(np.count_nonzero(diff_a2c & ~diff_puro)),
        },
        "limites": (
            "Mistura de RGB resolvido vermelho/azul, não leitura de máscaras "
            "de amostras individuais. Com 2 superfícies, depth-write de "
            "frente é testado pela segunda face desenhada atrás dela. "
            "Não representa a ordenação de toda a malha humana."
        ),
        "nao_homologado": True,
    }


def salvar_mapa(gl, vk, caminho):
    from PIL import Image
    g = gl[:, :, 0]
    v = vk[:, :, 0]
    if g.shape != (64, 64) or v.shape != (64, 64):
        raise ValueError("Mapa depth RGB exige 64x64")
    mapa = np.zeros((64, 64, 3), np.uint8)
    iguais = np.array_equal(gl.shape, vk.shape) and np.all(gl == vk, axis=2)
    mapa[iguais & (g > 0)] = (160, 160, 160)
    mapa[iguais & (g == 0)] = (30, 50, 110)
    mapa[g > v] = (255, 60, 70)
    mapa[v > g] = (35, 235, 255)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mapa, mode="RGB").resize(
        (512, 512), Image.Resampling.NEAREST
    ).save(caminho)
    return {
        "arquivo": str(caminho),
        "sha256_png": hashlib.sha256(caminho.read_bytes()).hexdigest(),
        "ampliacao_sem_interpolacao": 8,
        "legenda": (
            "cinza RGB igual com vermelho; azul escuro RGB igual no fundo; "
            "vermelho mais R em GL; ciano mais R em Vulkan"
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--png-msaa", type=Path, required=True)
    p.add_argument("--png-a2c", type=Path, required=True)
    args = p.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    if (
        gl.get("resultado_a2c") != "EXECUTADO_COM_MSAA_4X"
        or vk.get("suporte_msaa", {}).get("disponivel") is not True
    ):
        raise ValueError("Suporte de MSAA4x do corpo não comprovado")
    fonte_gl = gl["auditoria_sintetica_sobreposicao"]
    fonte_vk = vk["auditoria_sintetica_sobreposicao"]
    rel = comparar_sobreposicao(fonte_gl, fonte_vk)
    imagens_gl = auditar_manifesto(fonte_gl, "OpenGL")
    imagens_vk = auditar_manifesto(fonte_vk, "Vulkan")
    rel["mapas"] = {
        "msaa_puro": salvar_mapa(
            imagens_gl["a2c_off_z_on"], imagens_vk["a2c_off_z_on"],
            args.png_msaa,
        ),
        "a2c_alpha128": salvar_mapa(
            imagens_gl["a2c_on_z_on"], imagens_vk["a2c_on_z_on"],
            args.png_a2c,
        ),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(rel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "tipo": rel["tipo"], "resultados": rel["resultados"],
        "analise": rel["analise"]
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
