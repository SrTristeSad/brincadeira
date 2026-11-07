"""A2C GL/Vulkan com e sem recebimento de sombras, sem homologação.

Este experimento compara *onde* o A2C altera a captura RGB com a iluminação
de sombras original ligada no Vulkan e com receiveShadows=False apenas no
draw da malha. O OpenGL original permanece intocado. A ausência de shadow
visibility no Vulkan deste controle NÃO iguala shaders, iluminação, sRGB,
rasterização ou a política final de sombras dos dois renderizadores.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from mapear_efeito_a2c_rgb import criar_mapa, ler_captura, mascara_efeito


CASOS = {
    "off": ("4x_sem_a2c", "4x_sem_a2c_sem_sombras"),
    "on": ("4x_com_a2c", "4x_com_a2c_sem_sombras"),
}


def intersecao_sobre_uniao(a, b):
    """IoU binária; 1.0 para duas máscaras vazias."""
    a, b = np.asarray(a), np.asarray(b)
    if (a.shape != b.shape or a.dtype != bool or b.dtype != bool
            or a.ndim != 2):
        raise ValueError("IoU exige máscaras booleanas HxW iguais")
    uniao = int(np.count_nonzero(a | b))
    intersecao = int(np.count_nonzero(a & b))
    return {
        "intersecao": intersecao,
        "uniao": uniao,
        "iou": float(intersecao / uniao) if uniao else 1.0,
        "somente_a": int(np.count_nonzero(a & ~b)),
        "somente_b": int(np.count_nonzero(b & ~a)),
    }


def medir_efeito_sombras(gl_off, gl_on, vk_off, vk_on,
                        vk_off_sem, vk_on_sem, *, tolerancia=8):
    entradas = (gl_off, gl_on, vk_off, vk_on, vk_off_sem, vk_on_sem)
    if not all(
        isinstance(p, np.ndarray) and p.dtype == np.uint8
        and p.ndim == 3 and p.shape[2] == 3
        and p.shape == entradas[0].shape for p in entradas
    ):
        raise ValueError("Todos os seis PNGs precisam de RGB uint8 HxWx3 comum")
    if tolerancia < 0 or tolerancia > 255:
        raise ValueError("Tolerância RGB inválida")
    gl_mask = mascara_efeito(gl_off, gl_on, tolerancia=tolerancia)
    vk_mask = mascara_efeito(vk_off, vk_on, tolerancia=tolerancia)
    vk_sem_mask = mascara_efeito(
        vk_off_sem, vk_on_sem, tolerancia=tolerancia
    )
    sombra_off = mascara_efeito(vk_off, vk_off_sem, tolerancia=tolerancia)
    sombra_on = mascara_efeito(vk_on, vk_on_sem, tolerancia=tolerancia)
    return {
        "tipo": "ISOLAMENTO_RECEIVE_SHADOWS_A2C_MSAA_4X",
        "nao_homologado": True,
        "tolerancia_rgb": int(tolerancia),
        "dimensoes": [int(gl_off.shape[1]), int(gl_off.shape[0])],
        "pixels_efeito_a2c_gl": int(gl_mask.sum()),
        "pixels_efeito_a2c_vk_com_sombras": int(vk_mask.sum()),
        "pixels_efeito_a2c_vk_sem_sombras": int(vk_sem_mask.sum()),
        "comparacao_a2c_gl_vk_com_sombras": intersecao_sobre_uniao(
            gl_mask, vk_mask
        ),
        "comparacao_a2c_gl_vk_sem_sombras": intersecao_sobre_uniao(
            gl_mask, vk_sem_mask
        ),
        "comparacao_a2c_vk_sombras_on_off": intersecao_sobre_uniao(
            vk_mask, vk_sem_mask
        ),
        "pixels_alterados_ao_remover_sombras_a2c_off": int(sombra_off.sum()),
        "pixels_alterados_ao_remover_sombras_a2c_on": int(sombra_on.sum()),
        "nota": (
            "Mede suportes de mudanças RGB intrabackend, não diferença "
            "de cores absolutas GL/VK. Não iguala gamma/sRGB nem os shaders. "
            "IoU não é porcentagem de paridade visual ou amostras cobertas."
        ),
    }, {
        "gl": gl_mask,
        "vk_com_sombras": vk_mask,
        "vk_sem_sombras": vk_sem_mask,
    }


def auditar_controles(gl, vk, pareamento):
    if pareamento.get("estado") != "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS":
        raise ValueError("Pareamento GL/Vulkan anterior não foi validado")
    if (gl.get("backend") != "OpenGL" or vk.get("backend") != "Vulkan"
            or gl.get("estado") != "CAPTURADO"
            or vk.get("estado") != "OBSERVADO"):
        raise ValueError("Backend ou manifestos inesperados")
    if gl.get("dimensoes_imagem") != [1024, 768] or vk.get("dimensoes_imagem") != [1024, 768]:
        raise ValueError("Dimensões do ensaio não coincidem")
    if gl.get("camera") != vk.get("camera"):
        raise ValueError("Câmeras de referência diferentes")
    for chave in ("sha256_png", "sha256_rgba", "alfa_textura"):
        if gl["textura_controle"][chave] != vk["textura_controle"][chave]:
            raise ValueError("Textura difusa não foi pareada: " + chave)
    for estado, (base, sem_sombra) in CASOS.items():
        a2c = estado == "on"
        controle_gl = gl["controles"].get(base)
        if not controle_gl or controle_gl.get("a2c_elegivel") is not a2c:
            raise ValueError("Controle GL não corresponde ao A2C exigido")
        for nome, recebe_sombras in ((base, True), (sem_sombra, False)):
            c = vk["controles"].get(nome)
            if not c:
                raise ValueError("Falta controle Vulkan: " + nome)
            if not (
                c.get("amostras") == 4
                and c.get("captura_rgb") is True
                and c.get("alfa_textura") == 128
                and c.get("sha256_textura_png") == vk["textura_controle"]["sha256_png"]
                and c.get("nTransparentPrimitives", 0) > 0
                and c.get("pipeline_chave_cache_confirmada") is True
                and c.get("pipeline_a2c_observado") is a2c
                and c.get("a2c_elegivel") is a2c
                and c.get("blend_habilitado_observado") is (not a2c)
                and c.get("escrita_z_observada") is a2c
                and c.get("controle_sombras_desligadas") is (not recebe_sombras)
                and c.get("recebe_sombras_material_observado") is recebe_sombras
            ):
                raise ValueError("Estado de draw Vulkan inválido: " + nome)
            rastros = c.get("rastros_pipeline_corpo") or []
            if not rastros or not all(
                d.get("recebe_sombras_material_observado") is recebe_sombras
                and d.get("a2c_calculado") is a2c
                and d.get("blend_habilitado_previsto") is (not a2c)
                and d.get("escrita_z_prevista") is a2c
                for d in rastros
            ):
                raise ValueError("Spy de estado Vulkan inconsistente: " + nome)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--pareamento", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--png-com-sombras", type=Path, required=True)
    parser.add_argument("--png-sem-sombras", type=Path, required=True)
    args = parser.parse_args()

    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    pareado = json.loads(args.pareamento.read_text(encoding="utf-8"))
    auditar_controles(gl, vk, pareado)

    gl_off, gl_on = [
        ler_captura(gl["controles"][nome])
        for nome in ("4x_sem_a2c", "4x_com_a2c")
    ]
    vk_off, vk_on = [
        ler_captura(vk["controles"][nome])
        for nome in ("4x_sem_a2c", "4x_com_a2c")
    ]
    vk_off_sem, vk_on_sem = [
        ler_captura(vk["controles"][nome])
        for nome in ("4x_sem_a2c_sem_sombras", "4x_com_a2c_sem_sombras")
    ]
    resultado, mascaras = medir_efeito_sombras(
        gl_off, gl_on, vk_off, vk_on, vk_off_sem, vk_on_sem
    )
    from PIL import Image
    for img_path, mascara in (
        (args.png_com_sombras, mascaras["vk_com_sombras"]),
        (args.png_sem_sombras, mascaras["vk_sem_sombras"]),
    ):
        img_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(
            criar_mapa(mascaras["gl"], mascara), mode="RGB"
        ).save(img_path)
        resultado[
            "mapa_gl_vs_vk_" + (
                "com_sombras" if img_path == args.png_com_sombras else "sem_sombras"
            )
        ] = {
            "arquivo": str(img_path),
            "sha256_png": hashlib.sha256(img_path.read_bytes()).hexdigest(),
        }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
