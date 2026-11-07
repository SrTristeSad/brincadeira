"""Diagnóstico explícito OpenGL × Vulkan: bruto e transformações de canais.

NUNCA normaliza arquivos fonte in-place. Métricas transformadas não homologam
paridade e não mudam a renderização do produto. Exige PNGs da cena real.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from compare_portable_frames import pixels
from comparar_opengl_vulkan import comparar_pixels, salvar_mapa_diferencas


def trocar_vermelho_azul(imagem):
    dados = np.asarray(imagem)
    if dados.ndim != 3 or dados.shape[-1] != 4 or dados.dtype != np.uint8:
        raise ValueError("Imagem deve ser RGBA uint8")
    return np.ascontiguousarray(dados[:, :, [2, 1, 0, 3]])


def decodificar_srgb_rgb(imagem):
    dados = np.asarray(imagem)
    if dados.ndim != 3 or dados.shape[-1] != 4 or dados.dtype != np.uint8:
        raise ValueError("Imagem deve ser RGBA uint8")
    result = dados.copy()
    srgb = dados[:, :, :3].astype(np.float64) / 255.0
    linear = np.where(
        srgb <= 0.04045, srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4,
    )
    result[:, :, :3] = np.clip(np.rint(linear * 255), 0, 255).astype(np.uint8)
    return result


def _camera_igual(a, b, eps=1e-5):
    campos = ("fov", "centro", "radius", "projecao", "near", "far", "zoom",
              "rotacao_horizontal", "inclinacao_vertical", "translation")
    resultado = {}
    for campo in campos:
        try:
            v1, v2 = np.asarray(a[campo], dtype=np.float64), np.asarray(b[campo], dtype=np.float64)
            resultado[campo] = bool(v1.shape == v2.shape and np.max(np.abs(v1-v2)) <= eps)
        except (KeyError, TypeError, ValueError):
            resultado[campo] = False
    for campo in ("view", "proj"):
        try:
            v1, v2 = np.asarray(a[campo], dtype=np.float64), np.asarray(b[campo], dtype=np.float64)
            resultado[campo] = bool(v1.shape == (4, 4) and v2.shape == (4, 4)
                                     and np.max(np.abs(v1-v2)) <= eps)
        except (KeyError, TypeError, ValueError):
            resultado[campo] = False
    return resultado


def avaliar(ref_png, vulkan_png, ref_meta, vulkan_meta, saida, diretorio_diff=None,
           ref_sem_especular=None, vk_sem_especular=None,
           ref_sem_sombras=None, vk_sem_sombras=None,
           ref_so_difusa=None, vk_so_difusa=None,
           vk_luz_eye_legada=None, vk_luz_eye_legada_so_difusa=None):
    registro_ref = json.loads(Path(ref_meta).read_text(encoding="utf-8"))
    registro_vk = json.loads(Path(vulkan_meta).read_text(encoding="utf-8"))
    if registro_ref.get("estado") != "CAPTURADO":
        raise ValueError("Referência OpenGL sem captura válida")
    if registro_vk.get("estado") != "OBSERVADO":
        raise ValueError("Candidato Vulkan sem observação 1024x768")
    ref, vk = pixels(Path(ref_png)), pixels(Path(vulkan_png))
    if ref.shape != (768, 1024, 4) or vk.shape != ref.shape:
        raise ValueError(f"Resoluções distintas: ref {ref.shape} Vulkan {vk.shape}")
    camera = _camera_igual(registro_ref.get("camera", {}), registro_vk.get("camera", {}))
    nome_ref = registro_ref.get("material", {}).get("shader", {}).get("nome")
    nome_vk = registro_vk.get("estado_material_phong_on", {}).get("shader", {}).get("nome")
    cfg_ref = registro_ref.get("material", {}).get("shaderDefines", [])
    cfg_vk = registro_vk.get("estado_material_phong_on", {}).get("shaderDefines", [])
    difusa_ref = registro_ref.get("material", {}).get("mapas", {}).get("diffuseTexture")
    difusa_vk = registro_vk.get("estado_material_phong_on", {}).get("mapas", {}).get("diffuseTexture")
    dados_identicos = (
        nome_ref == nome_vk == "phong"
        and cfg_ref == cfg_vk
        and difusa_ref == difusa_vk
    )
    iluminacao_igual = registro_ref.get("iluminacao") == registro_vk.get("iluminacao")
    camera_igual = all(camera.values())

    variantes = {
        "bruto": (ref, vk),
        "gl_troca_rb_apenas": (trocar_vermelho_azul(ref), vk),
        "vk_srgb_para_linear_apenas": (ref, decodificar_srgb_rgb(vk)),
        "gl_troca_rb_e_vk_srgb_para_linear": (
            trocar_vermelho_azul(ref), decodificar_srgb_rgb(vk),
        ),
    }
    if (ref_sem_especular is None) != (vk_sem_especular is None):
        raise ValueError("Capturas sem especular precisam ser fornecidas em par")
    if ref_sem_especular is not None:
        if not (registro_ref.get("captura_especular_desligado") is True
                and registro_vk.get("captura_especular_desligado") is True):
            raise ValueError("Manifestos não confirmam capturas sem especular")
        estado_ref = registro_ref.get("material_sem_especular", {})
        estado_vk = registro_vk.get("estado_material_phong_sem_especular", {})
        if (estado_ref.get("specularColor") != [0.0, 0.0, 0.0]
                or estado_vk.get("specularColor") != [0.0, 0.0, 0.0]):
            raise ValueError("Capturas de controle precisam de especular zero")
        no_ref, no_vk = pixels(Path(ref_sem_especular)), pixels(Path(vk_sem_especular))
        if no_ref.shape != ref.shape or no_vk.shape != vk.shape:
            raise ValueError("Controles sem especular têm dimensões distintas")
        variantes.update({
            "sem_especular_bruto": (no_ref, no_vk),
            "sem_especular_gl_rb_e_vk_linear": (
                trocar_vermelho_azul(no_ref), decodificar_srgb_rgb(no_vk)
            )
        })
    if (ref_sem_sombras is None) != (vk_sem_sombras is None):
        raise ValueError("Controles sem sombra precisam ser fornecidos em par")
    if ref_sem_sombras is not None:
        if not (registro_ref.get("captura_sombras_desligadas") is True
                and registro_vk.get("captura_sombras_desligadas") is True):
            raise ValueError("Manifestos não confirmam controles sem sombra")
        ref_estado = registro_ref.get("material_sem_sombras", {})
        vk_estado = registro_vk.get("estado_material_phong_sem_sombras", {})
        if (ref_estado.get("receiveShadows") is not False
                or vk_estado.get("receiveShadows") is not False):
            raise ValueError("Controles de sombra exigem receiveShadows=False")
        no_ref, no_vk = pixels(Path(ref_sem_sombras)), pixels(Path(vk_sem_sombras))
        if no_ref.shape != ref.shape or no_vk.shape != vk.shape:
            raise ValueError("Controles sem sombra têm resolução inválida")
        variantes.update({
            "sem_sombras_bruto": (no_ref, no_vk),
            "sem_sombras_gl_rb_e_vk_linear": (
                trocar_vermelho_azul(no_ref), decodificar_srgb_rgb(no_vk)
            )
        })
    if (ref_so_difusa is None) != (vk_so_difusa is None):
        raise ValueError("Controles de difusa precisam ser fornecidos em par")
    if ref_so_difusa is not None:
        if not (registro_ref.get("captura_so_difusa") is True
                and registro_vk.get("captura_so_difusa") is True):
            raise ValueError("Manifestos não confirmam captura só difusa")
        estado_r = registro_ref.get("material_so_difusa", {})
        estado_v = registro_vk.get("estado_material_phong_so_difusa", {})
        for estado in (estado_r, estado_v):
            if (estado.get("ambientColor") != [0.0, 0.0, 0.0]
                    or estado.get("specularColor") != [0.0, 0.0, 0.0]
                    or estado.get("receiveShadows") is not False):
                raise ValueError("Experimento só difuso não isolou ambiente/especular/sombra")
        so_ref, so_vk = pixels(Path(ref_so_difusa)), pixels(Path(vk_so_difusa))
        if so_ref.shape != ref.shape or so_vk.shape != vk.shape:
            raise ValueError("Capturas só difusas inválidas")
        variantes.update({
            "so_difusa_bruto": (so_ref, so_vk),
            "so_difusa_gl_rb_e_vk_linear": (
                trocar_vermelho_azul(so_ref), decodificar_srgb_rgb(so_vk)
            ),
        })
    if ((vk_luz_eye_legada is None)
            != (vk_luz_eye_legada_so_difusa is None)):
        raise ValueError("Controle de luz eye precisa de dois PNGs Vulkan")
    if vk_luz_eye_legada is not None:
        if registro_vk.get("captura_luz_eye_legada") is not True:
            raise ValueError("Captura de luz eye não confirmada no manifesto Vulkan")
        gl_estado = registro_ref.get("estado_gl_luz", {})
        vk_luz = registro_vk.get("luz_eye_legada", {})
        if gl_estado.get("observado") is not True:
            raise ValueError("GL real não registrou a luz GL_LIGHT0 em espaço de câmera")
        eye = np.asarray(gl_estado["posicao_luz_eye_gl"], np.float64)
        pos_reproduzida = np.asarray(vk_luz.get("posicao_eye_reproduzida", []), np.float64)
        if eye.shape != (4,) or pos_reproduzida.shape != (3,) or not np.allclose(
                eye[:3], pos_reproduzida, atol=1e-5, rtol=0):
            raise ValueError("Controle Vulkan não reproduziu a luz GL realmente observada")
        world = np.asarray(vk_luz["posicao_world_compensada"], np.float64)
        view = np.asarray(registro_vk["camera"]["view"], np.float64)
        if world.shape != (3,) or not np.allclose(
                view @ [*world,1.], eye, atol=1e-5, rtol=0):
            raise ValueError("Luz compensada não está na posição eye do OpenGL")
        g = pixels(Path(vk_luz_eye_legada))
        d = pixels(Path(vk_luz_eye_legada_so_difusa))
        if g.shape != ref.shape or d.shape != ref.shape:
            raise ValueError("PNG Vulkan com luz compensada tem resolução errada")
        variantes["vk_luz_eye_legacy_bruto"] = (ref, g)
        variantes["vk_luz_eye_legacy_normalizado"] = (
            trocar_vermelho_azul(ref), decodificar_srgb_rgb(g)
        )
        if ref_so_difusa is None:
            raise ValueError("O controle só difuso OpenGL é necessário")
        ref_d = pixels(Path(ref_so_difusa))
        variantes["vk_luz_eye_legacy_so_difusa_normalizado"] = (
            trocar_vermelho_azul(ref_d), decodificar_srgb_rgb(d)
        )
    metricas = {}
    for nome, (a,b) in variantes.items():
        m = comparar_pixels(a, b, tolerancia=8, fracao_maxima=0.02)
        alpha_mismatch = m["pixels_alfa_diferente"] / m["pixels_total"]
        m["alpha_divergencia_fracao"] = alpha_mismatch
        m["limites_propostos_todos_satisfeitos"] = bool(
            m["fracao_divergente"] <= .02
            and m["erro_medio_rgb"] <= 3.
            and m["intersecao_uniao_cobertura_alfa"] >= .995
            and alpha_mismatch <= .005
        )
        m["alerta_alfa"] = "Ambos os PNGs são RGB; alfa preenchido artificialmente em 255"
        if nome in ("gl_troca_rb_e_vk_srgb_para_linear",
                     "so_difusa_gl_rb_e_vk_linear",
                     "vk_luz_eye_legacy_normalizado",
                     "vk_luz_eye_legacy_so_difusa_normalizado"):
            # Máscara luminância heurística. NÃO é cobertura alfa.
            cor_a, cor_b = a[:, :, :3].astype(np.int16), b[:, :, :3].astype(np.int16)
            regiao = np.any(np.abs(cor_a - 128) > 8, axis=-1) | np.any(
                np.abs(cor_b - 128) > 8, axis=-1
            )
            m["regiao_heuristica_corpo"] = {
                "pixels": int(np.count_nonzero(regiao)),
                "erro_medio_rgb": float(np.mean(np.abs(cor_a[regiao] - cor_b[regiao])))
                if np.any(regiao) else None,
                "erro_assinado_rgb_por_canal": (
                    (cor_a[regiao] - cor_b[regiao]).mean(axis=0).tolist()
                    if np.any(regiao) else None
                ),
                "aviso": "Região por contraste com cinza 128, não alpha mask.",
            }
        metricas[nome] = m
    if diretorio_diff:
        diretorio_diff = Path(diretorio_diff)
        diretorio_diff.mkdir(parents=True, exist_ok=True)
        salvar_mapa_diferencas(ref, vk, diretorio_diff / "phong-bruto-diff.png")
        a, b = variantes["gl_troca_rb_e_vk_srgb_para_linear"]
        salvar_mapa_diferencas(a, b, diretorio_diff / "phong-normalizacoes-diff.png")
        if "sem_especular_gl_rb_e_vk_linear" in variantes:
            a, b = variantes["sem_especular_gl_rb_e_vk_linear"]
            salvar_mapa_diferencas(
                a, b, diretorio_diff / "phong-sem-especular-normalizacoes-diff.png"
            )
        if "sem_sombras_gl_rb_e_vk_linear" in variantes:
            a, b = variantes["sem_sombras_gl_rb_e_vk_linear"]
            salvar_mapa_diferencas(
                a, b, diretorio_diff / "phong-sem-sombras-normalizacoes-diff.png"
            )
        if "so_difusa_gl_rb_e_vk_linear" in variantes:
            a, b = variantes["so_difusa_gl_rb_e_vk_linear"]
            salvar_mapa_diferencas(
                a, b, diretorio_diff / "phong-so-difusa-normalizacoes-diff.png"
            )
        for nome, arquivo in (
            ("vk_luz_eye_legacy_normalizado", "phong-luz-eye-legacy-diff.png"),
            ("vk_luz_eye_legacy_so_difusa_normalizado", "phong-luz-eye-legacy-so-difusa-diff.png"),
        ):
            if nome in variantes:
                a, b = variantes[nome]
                salvar_mapa_diferencas(a, b, diretorio_diff / arquivo)
    geo_ref = registro_ref.get("geometria")
    geo_vk = registro_vk.get("geometria")
    geo_ok = isinstance(geo_ref, dict) and isinstance(geo_vk, dict)
    geo_campos = ("posicoes", "normais", "primitivas")
    geo_checks = {
        nome: bool(
            geo_ok and geo_ref.get("assinaturas", {}).get(nome)
            == geo_vk.get("assinaturas", {}).get(nome)
        ) for nome in geo_campos
    }
    geo_id = bool(geo_ok and all(geo_checks.values())
                  and geo_ref.get("quantidade_vertices") == geo_vk.get("quantidade_vertices")
                  and geo_ref.get("quantidade_faces") == geo_vk.get("quantidade_faces"))
    condicoes = {
        "geometria": {
            "iguais": geo_id,
            "assinaturas_iguais": geo_checks,
            "referencia": geo_ref,
            "vulkan": geo_vk,
        },
        "luz_eye_gl_registrada": registro_ref.get("estado_gl_luz"),
        "camera": camera,
        "camera_totalmente_igual": camera_igual,
        "shader_material_e_defines_iguais": dados_identicos,
        "iluminacao_registrada_igual": iluminacao_igual,
        "shaders": {"opengl": nome_ref, "vulkan": nome_vk},
        "shaderDefines": {"opengl": cfg_ref, "vulkan": cfg_vk},
        "mapas_diffuse": {"opengl": difusa_ref, "vulkan": difusa_vk},
        "dimensoes_logicas_originais": {
            "opengl": [registro_ref.get("G_windowWidth"), registro_ref.get("G_windowHeight")],
            "vulkan": [registro_vk.get("G_windowWidth"), registro_vk.get("G_windowHeight")],
        },
    }
    entrada_par_comparavel = bool(camera_igual and dados_identicos
                                 and iluminacao_igual and geo_id)
    resultado = {
        "tipo": "DIAGNOSTICO_PAREADO_PHONG",
        "status": "PAR_COMPARAVEL_PARA_DIAGNOSTICO" if entrada_par_comparavel else "ENTRADAS_NAO_COMPROVADAS_EQUIVALENTES",
        "comparacao_mecanismos_apenas": True,
        "paridade_com_original_homologada": False,
        "fontes_nao_modificadas": True,
        "controle_sem_especular_presente": ref_sem_especular is not None,
        "controle_sem_sombras_presente": ref_sem_sombras is not None,
        "controle_so_difusa_presente": ref_so_difusa is not None,
        "controle_luz_eye_legada_presente": vk_luz_eye_legada is not None,
        "motivo_normalizacoes": [
            "O upstream usa glReadPixels GL_RGBA mas inverte R/B no array retornado.",
            "O framebuffer Vulkan offscreen foi observado em rgba8unorm-srgb.",
            "As transformações abaixo são APENAS experiências pós-captura; não são correções aprovadas.",
        ],
        "condicoes": condicoes,
        "metricas": metricas,
        "aviso": "Exit code 0 do comparador não substitui conferir todas as métricas e imagens.",
    }
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)
    return resultado


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--manifesto-opengl", type=Path, required=True)
    p.add_argument("--manifesto-vulkan", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--diff-dir", type=Path)
    p.add_argument("--opengl-sem-especular", type=Path)
    p.add_argument("--vulkan-sem-especular", type=Path)
    p.add_argument("--opengl-sem-sombras", type=Path)
    p.add_argument("--vulkan-sem-sombras", type=Path)
    p.add_argument("--opengl-so-difusa", type=Path)
    p.add_argument("--vulkan-so-difusa", type=Path)
    p.add_argument("--vulkan-luz-eye-legada", type=Path)
    p.add_argument("--vulkan-luz-eye-legada-so-difusa", type=Path)
    args = p.parse_args()
    avaliar(args.opengl, args.vulkan, args.manifesto_opengl,
            args.manifesto_vulkan, args.json, args.diff_dir,
            args.opengl_sem_especular, args.vulkan_sem_especular,
            args.opengl_sem_sombras, args.vulkan_sem_sombras,
            args.opengl_so_difusa, args.vulkan_so_difusa,
            args.vulkan_luz_eye_legada, args.vulkan_luz_eye_legada_so_difusa)


if __name__ == "__main__":
    main()
