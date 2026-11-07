"""Diagnostica distância e magnitude do resíduo A2C GL/Vulkan.

Não desloca pixels, não atribui automaticamente causa geométrica à diferença
e não modifica a rasterização. Usa capturas RGB e hashes dos manifestos.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from comparar_sombras_a2c_gl_vulkan import auditar_controles
from mapear_diferenca_depth_a2c import componentes_8_conexos
from mapear_efeito_a2c_rgb import ler_captura, mascara_efeito


RAIOS = (1, 2, 5)
LIMIARES = (2, 4, 8, 12, 16, 24)


def dilatar_quadrado(mask, raio):
    """Distância de Chebyshev (8 vizinhos), sem wraparound nem SciPy."""
    m = np.asarray(mask)
    if m.ndim != 2 or m.dtype != bool:
        raise ValueError("A máscara deve ser booleana HxW")
    if type(raio) is not int or raio < 0:
        raise ValueError("O raio deve ser inteiro não negativo")
    resultado = m.copy()
    h, w = m.shape
    for _ in range(raio):
        pad = np.pad(resultado, 1, mode="constant", constant_values=False)
        expandido = np.zeros_like(m)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                expandido |= pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        resultado = expandido
    return resultado


def caracterizar_residuo(mascara_gl, mascara_vk, *, raios=RAIOS):
    gl = np.asarray(mascara_gl)
    vk = np.asarray(mascara_vk)
    if (gl.ndim != 2 or vk.shape != gl.shape
            or gl.dtype != bool or vk.dtype != bool):
        raise ValueError("Duas máscaras booleanas HxW idênticas necessárias")
    if not raios or sorted(set(raios)) != list(raios) or raios[0] < 1:
        raise ValueError("Raios devem ser positivos, únicos e ordenados")
    so_gl = gl & ~vk
    so_vk = vk & ~gl
    inter = gl & vk
    total_gl, total_vk = int(so_gl.sum()), int(so_vk.sum())
    comparacoes = {}
    for raio in raios:
        prox_gl = so_gl & dilatar_quadrado(vk, raio)
        prox_vk = so_vk & dilatar_quadrado(gl, raio)
        q_gl, q_vk = int(prox_gl.sum()), int(prox_vk.sum())
        comparacoes[str(raio)] = {
            "gl_proximos": q_gl,
            "vk_proximos": q_vk,
            "gl_distantes": total_gl - q_gl,
            "vk_distantes": total_vk - q_vk,
            "total_proximos": q_gl + q_vk,
            "total_distantes": total_gl + total_vk - q_gl - q_vk,
        }
    raio_max = raios[-1]
    longe_gl = so_gl & ~dilatar_quadrado(vk, raio_max)
    longe_vk = so_vk & ~dilatar_quadrado(gl, raio_max)
    dados = {
        "raios_chebyshev_px": list(raios),
        "pixels_intersecao": int(inter.sum()),
        "pixels_exclusivos_gl": total_gl,
        "pixels_exclusivos_vk": total_vk,
        "pixels_exclusivos_total": total_gl + total_vk,
        "vizinhança": comparacoes,
        "aglomerados_distantes": {
            "limiar_distancia_maior_que_px": raio_max,
            "gl": componentes_8_conexos(longe_gl)[:20],
            "vk": componentes_8_conexos(longe_vk)[:20],
        },
    }
    return dados, {
        "intersecao": inter,
        "so_gl": so_gl,
        "so_vk": so_vk,
        "gl_distante": longe_gl,
        "vk_distante": longe_vk,
    }


def mapa_residuo(camadas):
    """Um PNG RGB com proximidade e exceções distantes codificadas por cor."""
    inter = camadas["intersecao"]
    gl = camadas["so_gl"]
    vk = camadas["so_vk"]
    gl_longe = camadas["gl_distante"]
    vk_longe = camadas["vk_distante"]
    for m in (gl, vk, gl_longe, vk_longe):
        if m.dtype != bool or m.shape != inter.shape:
            raise ValueError("Camadas incompatíveis")
    imagem = np.zeros((*inter.shape, 3), np.uint8)
    imagem[inter] = (185, 185, 185)
    imagem[gl] = (145, 50, 50)
    imagem[vk] = (35, 105, 145)
    imagem[gl_longe] = (255, 75, 75)
    imagem[vk_longe] = (35, 235, 255)
    return imagem


def magnitudes_opostas(off_gl, on_gl, off_vk, on_vk, camadas):
    """Quando só um backend supera 8, mede o delta do OUTRO (0..8)."""
    arrays = [np.asarray(x) for x in (off_gl, on_gl, off_vk, on_vk)]
    if not all(
        x.dtype == np.uint8 and x.ndim == 3 and x.shape == arrays[0].shape
        and x.shape[2] == 3 for x in arrays
    ):
        raise ValueError("Imagens RGB uint8 incompatíveis")
    delta_gl = np.max(abs(arrays[1].astype(np.int16) -
                          arrays[0].astype(np.int16)), axis=2)
    delta_vk = np.max(abs(arrays[3].astype(np.int16) -
                          arrays[2].astype(np.int16)), axis=2)
    def medir(mascara, delta_outro):
        valores = delta_outro[mascara]
        return {
            "pixels": int(len(valores)),
            "outro_delta_zero": int(np.count_nonzero(valores == 0)),
            "outro_delta_1_a_4": int(np.count_nonzero(
                (valores >= 1) & (valores <= 4)
            )),
            "outro_delta_5_a_8": int(np.count_nonzero(
                (valores >= 5) & (valores <= 8)
            )),
        }
    return {
        "exclusivos_gl_magnitude_vulkan": medir(camadas["so_gl"], delta_vk),
        "exclusivos_vk_magnitude_opengl": medir(camadas["so_vk"], delta_gl),
    }


def diagnosticar(gl_off, gl_on, vk_off, vk_on, vk_off_sem, vk_on_sem):
    imagens = (gl_off, gl_on, vk_off, vk_on, vk_off_sem, vk_on_sem)
    if not all(
        isinstance(x, np.ndarray) and x.dtype == np.uint8 and x.ndim == 3
        and x.shape == imagens[0].shape and x.shape[2] == 3
        for x in imagens
    ):
        raise ValueError("Seis imagens RGB uint8 do mesmo tamanho necessárias")
    tabelas = {}
    mapas = {}
    for limiar in LIMIARES:
        gl = mascara_efeito(gl_off, gl_on, tolerancia=limiar)
        for estado, antes, depois in (
            ("com_sombras", vk_off, vk_on),
            ("sem_sombras", vk_off_sem, vk_on_sem),
        ):
            vk = mascara_efeito(antes, depois, tolerancia=limiar)
            metrica, camadas = caracterizar_residuo(gl, vk)
            # Resumo por limiar, com detalhamento completo na tolerância 8.
            chave = f"{estado}_limiar_{limiar}"
            i, u = int((gl & vk).sum()), int((gl | vk).sum())
            resumo = {
                "pixels_gl": int(gl.sum()),
                "pixels_vk": int(vk.sum()),
                "iou": float(i / u) if u else 1.0,
                "exclusivos_total": metrica["pixels_exclusivos_total"],
                "exclusivos_distantes_mais_5px":
                    metrica["vizinhança"]["5"]["total_distantes"],
            }
            tabelas[chave] = resumo
            if limiar == 8:
                resumo["decomposicao_espacial"] = metrica
                resumo["magnitude_delta_outro_backend"] = magnitudes_opostas(
                    gl_off, gl_on, antes, depois, camadas
                )
                mapas[estado] = mapa_residuo(camadas)
    return {
        "tipo": "RESIDUO_ESPACIAL_A2C_8_CONEXOS_SEM_HOMOLOGACAO",
        "nao_homologado": True,
        "dimensoes": [int(gl_off.shape[1]), int(gl_off.shape[0])],
        "limiares_rgb": list(LIMIARES),
        "resultados": tabelas,
        "legenda_mapa": {
            "cinza": "efeito em ambos",
            "vermelho_escuro": "somente GL a até 5px do efeito VK",
            "azul_escuro": "somente VK a até 5px do efeito GL",
            "vermelho_vivo": "somente GL a mais de 5px",
            "ciano_vivo": "somente VK a mais de 5px",
            "preto": "sem efeito em nenhum",
        },
        "limites": (
            "Distância de Chebyshev entre máscaras RGB ON/OFF, não entre "
            "contornos geométricos nem amostras MSAA. Um pixel exclusivo "
            "pode ser só efeito do limiar de cor. Não prova a causa."
        ),
    }, mapas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opengl", type=Path, required=True)
    p.add_argument("--vulkan", type=Path, required=True)
    p.add_argument("--pareamento", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--png-sem-sombras", type=Path, required=True)
    p.add_argument("--png-com-sombras", type=Path, required=True)
    args = p.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    pareado = json.loads(args.pareamento.read_text(encoding="utf-8"))
    auditar_controles(gl, vk, pareado)

    gl_off, gl_on = (
        ler_captura(gl["controles"][nome])
        for nome in ("4x_sem_a2c", "4x_com_a2c")
    )
    vk_off, vk_on = (
        ler_captura(vk["controles"][nome])
        for nome in ("4x_sem_a2c", "4x_com_a2c")
    )
    vk_off_sem, vk_on_sem = (
        ler_captura(vk["controles"][nome])
        for nome in ("4x_sem_a2c_sem_sombras", "4x_com_a2c_sem_sombras")
    )
    resultado, mapas = diagnosticar(
        gl_off, gl_on, vk_off, vk_on, vk_off_sem, vk_on_sem
    )
    from PIL import Image
    for estado, path in (
        ("com_sombras", args.png_com_sombras),
        ("sem_sombras", args.png_sem_sombras),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(mapas[estado], mode="RGB").save(path)
        resultado["mapa_" + estado] = {
            "arquivo": str(path),
            "sha256_png": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print("RESIDUO_A2C_GLVK " + json.dumps(
        {
            "com_sombras_8": resultado["resultados"]["com_sombras_limiar_8"],
            "sem_sombras_8": resultado["resultados"]["sem_sombras_limiar_8"],
        },
        ensure_ascii=False
    ), flush=True)


if __name__ == "__main__":
    main()
