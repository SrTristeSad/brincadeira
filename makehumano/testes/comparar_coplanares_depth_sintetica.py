"""Auditoria de duas faces coincidentes e quase coincidentes GL/Vulkan.

Sem pressupor sample positions iguais e sem homologar paridade do corpo.
Lê PNGs, confere hash do arquivo e RGB, estados de desenho, contrato de
depth no centro, efeito de ordem, restauração e testes de profundidade.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from contrato_coplanares_depth_sintetica import (
    CASOS_COPLANARES, DEPTH_AZUL, DEPTH_SEPARACAO,
    centro_esperado, classificar_centro, passos_desenho,
    vertices_face,
)


def ler_manifesto(doc, backend):
    if not (
        doc.get("backend") == backend
        and doc.get("tipo") == "COPLANARES_MSAA_Z_4X"
        and doc.get("nao_homologado") is True
        and set(doc.get("controles", {})) == {
            caso[0] for caso in CASOS_COPLANARES
        }
    ):
        raise ValueError("Manifesto coplanar inválido: " + backend)
    from PIL import Image
    imagens = {}
    for caso in CASOS_COPLANARES:
        nome, compare, a2c, z_write, ordem, separacao = caso
        registro = doc["controles"][nome]
        esperado = centro_esperado(compare, a2c, z_write, ordem, separacao)
        if not (
            registro.get("nome") == nome
            and registro.get("comparacao_depth") == compare
            and registro.get("a2c_vermelho") is a2c
            and registro.get("alfa_vermelho") == (128 if a2c else 255)
            and registro.get("escrita_z_vermelho") is z_write
            and registro.get("ordem") == ordem
            and registro.get("separacao_depth") == separacao
            and registro.get("depth_azul") == DEPTH_AZUL
            and registro.get("depth_vermelho") == DEPTH_AZUL - separacao
            and registro.get("vertices_vermelho") == vertices_face(
                "vermelho", separacao
            )
            and registro.get("vertices_azul") == vertices_face("azul", separacao)
            and registro.get("msaa") == 4
            and registro.get("formato_cor") == "rgba8unorm"
            and registro.get("blend") is False
            and registro.get("rastros") == passos_desenho(
                compare, a2c, z_write, ordem
            )
        ):
            raise ValueError("Estados do draw coplanar inválidos: " + nome)
        if backend == "OpenGL":
            if not (
                registro.get("amostras_fbo_observadas") == 4
                and registro.get("formato_depth_fbo") == "depth24"
                and registro.get("depth_range") == [0.0, 1.0]
            ):
                raise ValueError("GL FBO coplanar não comprovou MSAA/depth")
        elif not (
            registro.get("formato_depth_pipeline") == "depth24plus"
            and registro.get("amostras_depth_configuradas") == 4
        ):
            raise ValueError("Vulkan pipeline coplanar sem depth4x")
        arquivo = Path(registro["arquivo_png"])
        raw = arquivo.read_bytes()
        if hashlib.sha256(raw).hexdigest() != registro.get("sha256_png"):
            raise ValueError("PNG coplanar alterado: " + nome)
        with Image.open(arquivo) as im:
            if im.mode != "RGB" or im.size != (64, 64):
                raise ValueError("Imagem coplanar não é RGB8 64x64")
            rgb = np.ascontiguousarray(np.asarray(im))
        classe = classificar_centro(rgb)
        if not (
            classe == esperado
            and classe == registro.get("centro_classe")
            and [int(x) for x in rgb[32, 32]] == registro.get("centro_rgb")
            and hashlib.sha256(rgb.tobytes()).hexdigest()
                == registro.get("sha256_rgb")
            and int(np.count_nonzero(rgb[:, :, 0]))
                == registro.get("pixels_vermelho")
            and int(np.count_nonzero(rgb[:, :, 2]))
                == registro.get("pixels_azul")
            and int(np.count_nonzero(
                (rgb[:, :, 0] > 0) & (rgb[:, :, 2] > 0)
            )) == registro.get("pixels_mistos")
        ):
            raise ValueError(
                "Centro/bytes RGB coplanar incoerentes: " + backend + " " + nome
            )
        imagens[nome] = rgb

    for primeiro, segundo in (
        ("igual_less_on_z_on_vermelho_primeiro",
         "igual_less_on_z_on_repeticao"),
        ("perto_less_off_z_on_vermelho_primeiro",
         "perto_less_off_z_on_azul_primeiro"),
        ("perto_less_on_z_on_vermelho_primeiro",
         "perto_less_on_z_on_azul_primeiro"),
    ):
        if not np.array_equal(imagens[primeiro], imagens[segundo]):
            raise ValueError(
                "Ordem ou repetição alterou controle esperado: "
                + backend + " " + primeiro + " " + segundo
            )
    return imagens


def diferenca_rgb(a, b, mascara_borda=None):
    if (
        a.shape != (64, 64, 3) or b.shape != a.shape
        or a.dtype != np.uint8 or b.dtype != np.uint8
    ):
        raise ValueError("Delta coplanar exige duas imagens RGB8 64x64")
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    diferem = np.any(delta > 0, axis=2)
    result = {
        "pixels_rgb_diferentes": int(diferem.sum()),
        "delta_max_rgb": int(delta.max()),
    }
    if mascara_borda is not None:
        if mascara_borda.dtype != bool or mascara_borda.shape != (64, 64):
            raise ValueError("Máscara de borda coplanar incompatível")
        result["pixels_na_borda_msaa"] = int(np.count_nonzero(
            diferem & mascara_borda
        ))
        result["pixels_fora_borda_msaa"] = int(np.count_nonzero(
            diferem & ~mascara_borda
        ))
    return result


def comparar_coplanares(gl, vk):
    imgs_gl = ler_manifesto(gl, "OpenGL")
    imgs_vk = ler_manifesto(vk, "Vulkan")
    baseline = "igual_less_off_z_on_vermelho_primeiro"
    r_gl = imgs_gl[baseline][:, :, 0]
    r_vk = imgs_vk[baseline][:, :, 0]
    borda = ((r_gl > 0) & (r_gl < 255)) | ((r_vk > 0) & (r_vk < 255))
    resultados = {}
    for caso in CASOS_COPLANARES:
        nome, compare, a2c, z_write, ordem, separacao = caso
        resultados[nome] = {
            **diferenca_rgb(imgs_gl[nome], imgs_vk[nome], borda),
            "classe_centro_gl": gl["controles"][nome]["centro_classe"],
            "classe_centro_vk": vk["controles"][nome]["centro_classe"],
            "comparacao_z": compare,
            "a2c": a2c,
            "escrita_z": z_write,
            "ordem": ordem,
            "separacao_depth": separacao,
        }
    contrastes = {}
    for backend, img in (("gl", imgs_gl), ("vk", imgs_vk)):
        contrastes[backend] = {
            "less_vs_lequal_vermelho_primeiro": diferenca_rgb(
                img["igual_less_off_z_on_vermelho_primeiro"],
                img["igual_lequal_off_z_on_vermelho_primeiro"],
            ),
            "less_ordem_invertida": diferenca_rgb(
                img["igual_less_off_z_on_vermelho_primeiro"],
                img["igual_less_off_z_on_azul_primeiro"],
            ),
            "less_vs_z_off": diferenca_rgb(
                img["igual_less_off_z_on_vermelho_primeiro"],
                img["igual_less_off_z_off_vermelho_primeiro"],
            ),
            "coplanar_vs_proximo_azul_primeiro": diferenca_rgb(
                img["igual_less_off_z_on_azul_primeiro"],
                img["perto_less_off_z_on_azul_primeiro"],
            ),
            "a2c_coplanar_vs_proximo_azul_primeiro": diferenca_rgb(
                img["igual_less_on_z_on_azul_primeiro"],
                img["perto_less_on_z_on_azul_primeiro"],
            ),
            "repeticao_com_a2c": diferenca_rgb(
                img["igual_less_on_z_on_vermelho_primeiro"],
                img["igual_less_on_z_on_repeticao"],
            ),
        }
    return {
        "tipo": "COMPARACAO_COPLANARES_Z_MSAA4X",
        "estado": "CONTROLES_GPU_REAIS_COM_CONTRATO_VERIFICADO",
        "amostras": 4,
        "depth_azul": DEPTH_AZUL,
        "separacao_minima_depth": DEPTH_SEPARACAO,
        "bordas_msaa_uniao_pixels": int(borda.sum()),
        "resultados_gl_vs_vulkan": resultados,
        "contrastes_por_backend": contrastes,
        "nao_homologado": True,
        "ressalva": (
            "LESS, LESS_EQUAL, z-write, ordem e desnível 2^-18 "
            "foram isolados em duas faces sintéticas idênticas. Não mede "
            "amostras MSAA individualmente, não reproduz o shader Phong, "
            "z-fighting arbitrário nem a malha humana em produção."
        ),
    }


def main():
    from comparar_sobreposicao_depth_sintetica import salvar_mapa
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--png-less-a2c", type=Path, required=True)
    p.add_argument("--png-depth-proximo", type=Path, required=True)
    args = p.parse_args()
    manifest_gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    manifest_vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    if not (
        manifest_gl.get("resultado_a2c") == "EXECUTADO_COM_MSAA_4X"
        and manifest_vk.get("suporte_msaa", {}).get("disponivel") is True
    ):
        raise ValueError("MSAA4× do corpo não comprovado no harness")
    gl = manifest_gl["auditoria_sintetica_coplanares"]
    vk = manifest_vk["auditoria_sintetica_coplanares"]
    rel = comparar_coplanares(gl, vk)
    im_gl = ler_manifesto(gl, "OpenGL")
    im_vk = ler_manifesto(vk, "Vulkan")
    rel["mapas"] = {
        "iguais_a2c_less": salvar_mapa(
            im_gl["igual_less_on_z_on_vermelho_primeiro"],
            im_vk["igual_less_on_z_on_vermelho_primeiro"],
            args.png_less_a2c,
        ),
        "quase_coplanares_azul_primeiro": salvar_mapa(
            im_gl["perto_less_off_z_on_azul_primeiro"],
            im_vk["perto_less_off_z_on_azul_primeiro"],
            args.png_depth_proximo,
        ),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(rel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("COPLANARES_DEPTH: " + json.dumps({
        "resultados": rel["resultados_gl_vs_vulkan"],
        "contrastes_por_backend": rel["contrastes_por_backend"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
