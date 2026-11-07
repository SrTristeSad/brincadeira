"""Compara LOCALIZAÇÃO do efeito RGB A2C (ON-OFF) em GL e Vulkan.

Usa máscaras de mudança intrabackend, não diffs de cor absoluta GL vs Vulkan.
O mapa e as métricas são diagnósticos, não homologação de paridade visual.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def mascara_efeito(off, on, *, tolerancia=8):
    a = np.asarray(off)
    b = np.asarray(on)
    if a.shape != b.shape or a.ndim != 3 or a.shape[2] != 3:
        raise ValueError("Controles RGB precisam ter dimensões HxWx3 idênticas")
    if a.dtype != np.uint8 or b.dtype != np.uint8:
        raise ValueError("Controles RGB devem ter dtype uint8")
    if not 0 <= tolerancia <= 255:
        raise ValueError("Tolerância RGB inválida")
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return np.any(d > tolerancia, axis=2)


def dilatar_um_pixel(mask):
    m = np.asarray(mask)
    if m.ndim != 2 or m.dtype != bool:
        raise ValueError("Máscara precisa ser booleana e bidimensional")
    h, w = m.shape
    out = np.zeros_like(m)
    pad = np.pad(m, 1, mode="constant", constant_values=False)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    return out



def erodir_mascara(mask, *, pixels=5):
    """Erosão 8-conexa, sem SciPy (a CI só precisa de NumPy)."""
    m = np.asarray(mask)
    if m.ndim != 2 or m.dtype != bool or pixels < 0:
        raise ValueError("Máscara booleana 2D e erosão >= 0 necessárias")
    resultado = m.copy()
    h, w = m.shape
    for _ in range(pixels):
        padded = np.pad(resultado, 1, constant_values=False)
        erodida = np.ones_like(resultado)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                erodida &= padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        resultado = erodida
    return resultado


def deslocar_mascara(mask, dx, dy):
    """Deslocamento INTEIRO sem wraparound; fora do quadro vale False."""
    m = np.asarray(mask)
    if m.ndim != 2 or m.dtype != bool:
        raise ValueError("Máscara booleana 2D necessária")
    if not isinstance(dx, int) or not isinstance(dy, int):
        raise ValueError("Deslocamentos precisam ser inteiros")
    h, w = m.shape
    resultado = np.zeros_like(m)
    y0, y1 = max(0, dy), min(h, h + dy)
    x0, x1 = max(0, dx), min(w, w + dx)
    if y0 < y1 and x0 < x1:
        resultado[y0:y1, x0:x1] = m[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return resultado


def decompor_efeito_a2c(off_gl, on_gl, off_vk, on_vk, *,
                         tolerancia=8, limiar_fundo=10, erosao_pixels=5,
                         busca_deslocamento=2):
    """Auditoria espacial, SEM corrigir imagem, geometria ou cor dos backends.

    A região estimada de corpo é inferida separadamente pelo RGB do quadro
    A2C OFF menos a cor do canto: não é ground truth de silhueta/visibilidade.
    Os deltas intrabackend preservam diferenças de sRGB nos valores absolutos.
    """
    imgs = [np.asarray(v) for v in (off_gl, on_gl, off_vk, on_vk)]
    if not all(v.dtype == np.uint8 and v.ndim == 3 and v.shape == imgs[0].shape
               and v.shape[2] == 3 for v in imgs):
        raise ValueError("Quatro imagens RGB uint8 HxWx3 idênticas requeridas")
    if limiar_fundo < 0 or erosao_pixels < 0 or busca_deslocamento < 0:
        raise ValueError("Parâmetros espaciais inválidos")
    mg = mascara_efeito(off_gl, on_gl, tolerancia=tolerancia)
    mv = mascara_efeito(off_vk, on_vk, tolerancia=tolerancia)
    fundo_gl = imgs[0][0, 0].tolist()
    fundo_vk = imgs[2][0, 0].tolist()

    resultados_borda = {}
    for nome, indice, mudou in (("opengl", 0, mg), ("vulkan", 2, mv)):
        referencia = imgs[indice].astype(np.int16)
        fundo = referencia[0, 0]
        corpo_estimado = np.any(np.abs(referencia - fundo) > limiar_fundo, axis=2)
        interior = erodir_mascara(corpo_estimado, pixels=erosao_pixels)
        total = int(mudou.sum())
        zona_borda = int(np.count_nonzero(mudou & ~interior))
        resultados_borda[nome] = {
            "pixels_corpo_estimado": int(corpo_estimado.sum()),
            "pixels_efeito_fora_do_corpo_estimado":
                int(np.count_nonzero(mudou & ~corpo_estimado)),
            "pixels_efeito_na_borda_ou_exterior": zona_borda,
            "pixels_efeito_no_interior_estimado": int(np.count_nonzero(mudou & interior)),
            "fracao_efeito_na_borda_ou_exterior":
                float(zona_borda / total) if total else 0.0,
            "limiar_rgb_ao_fundo": int(limiar_fundo),
            "largura_erosao_px": int(erosao_pixels),
        }

    uniao = mg | mv
    inter = mg & mv
    iou_zero = float(inter.sum() / uniao.sum()) if uniao.any() else 1.0
    melhor_iou, melhor_dx, melhor_dy = iou_zero, 0, 0
    for dy in range(-busca_deslocamento, busca_deslocamento + 1):
        for dx in range(-busca_deslocamento, busca_deslocamento + 1):
            if not dx and not dy:
                continue
            transladada = deslocar_mascara(mg, int(dx), int(dy))
            u = np.count_nonzero(transladada | mv)
            i = np.count_nonzero(transladada & mv)
            valor = float(i / u) if u else 1.0
            if valor > melhor_iou + 1e-12:
                melhor_iou, melhor_dx, melhor_dy = valor, dx, dy

    deltas_gl = imgs[1].astype(np.int16) - imgs[0].astype(np.int16)
    deltas_vk = imgs[3].astype(np.int16) - imgs[2].astype(np.int16)
    vetores_gl, vetores_vk = deltas_gl[inter].astype(float), deltas_vk[inter].astype(float)
    if len(vetores_gl):
        produto = np.einsum("ij,ij->i", vetores_gl, vetores_vk)
        norma = np.linalg.norm(vetores_gl, axis=1) * np.linalg.norm(vetores_vk, axis=1)
        cos = produto / np.maximum(norma, 1e-12)
        estatisticas_delta = {
            "pixels_suporte_conjunto": int(len(cos)),
            "fracao_deltas_rgb_mesma_direcao_cos_gt_0_5": float(np.mean(cos > 0.5)),
            "fracao_deltas_rgb_direcao_oposta_cos_lt_menos_0_5":
                float(np.mean(cos < -0.5)),
            "cosseno_mediano_dos_deltas_rgb": float(np.median(cos)),
        }
    else:
        estatisticas_delta = {
            "pixels_suporte_conjunto": 0,
            "fracao_deltas_rgb_mesma_direcao_cos_gt_0_5": None,
            "fracao_deltas_rgb_direcao_oposta_cos_lt_menos_0_5": None,
            "cosseno_mediano_dos_deltas_rgb": None,
        }
    varredura = []
    for limite in (2, 4, 8, 12, 16, 24):
        g = mascara_efeito(off_gl, on_gl, tolerancia=limite)
        v = mascara_efeito(off_vk, on_vk, tolerancia=limite)
        inter_limite = int(np.count_nonzero(g & v))
        uniao_limite = int(np.count_nonzero(g | v))
        varredura.append({
            "limiar_rgb": limite,
            "pixels_gl": int(np.count_nonzero(g)),
            "pixels_vk": int(np.count_nonzero(v)),
            "intersecao": inter_limite,
            "uniao": uniao_limite,
            "iou": float(inter_limite / uniao_limite) if uniao_limite else 1.0,
        })
    metade = mg.shape[1] // 2
    return {
        "varredura_tolerancias_rgb": varredura,
        "nota_varredura": (
            "Limiar RGB aplicado em cada backend separadamente, sem linearizar sRGB. "
            "Variação de IoU não prova nem exclui erro de cobertura por amostra."
        ),
        "metodo": "limiar intrabackend ON-OFF; fundo inferido do canto; borda estimada, não geometria",
        "fundo_rgb_off_opengl": [int(x) for x in fundo_gl],
        "fundo_rgb_off_vulkan": [int(x) for x in fundo_vk],
        "borda_corpo_estimados": resultados_borda,
        "efeito_metade_esquerda_direita": {
            "opengl": [int(mg[:, :metade].sum()), int(mg[:, metade:].sum())],
            "vulkan": [int(mv[:, :metade].sum()), int(mv[:, metade:].sum())],
            "somente_opengl": [
                int(np.count_nonzero((mg & ~mv)[:, :metade])),
                int(np.count_nonzero((mg & ~mv)[:, metade:])),
            ],
            "somente_vulkan": [
                int(np.count_nonzero((mv & ~mg)[:, :metade])),
                int(np.count_nonzero((mv & ~mg)[:, metade:])),
            ],
        },
        "busca_translacao_inteira_diagnostica": {
            "raio_px": int(busca_deslocamento),
            "iou_sem_deslocamento": iou_zero,
            "iou_melhor": float(melhor_iou),
            "melhor_deslocamento_gl_para_vk_xy": [int(melhor_dx), int(melhor_dy)],
            "ganho_iou": float(melhor_iou - iou_zero),
            "nota": "A busca não desloca nem corrige os PNGs usados na medição original.",
        },
        "direcao_dos_deltas_na_intersecao": estatisticas_delta,
        "nao_homologado": True,
    }


def analisar_efeitos(off_gl, on_gl, off_vk, on_vk, *, tolerancia=8):
    mg = mascara_efeito(off_gl, on_gl, tolerancia=tolerancia)
    mv = mascara_efeito(off_vk, on_vk, tolerancia=tolerancia)
    if mg.shape != mv.shape:
        raise ValueError("Matrizes de GL e Vulkan possuem dimensões diferentes")
    inter = mg & mv
    uniao = mg | mv
    qtd_gl, qtd_vk = int(mg.sum()), int(mv.sum())
    qtd_inter, qtd_uniao = int(inter.sum()), int(uniao.sum())
    viz_gl, viz_vk = dilatar_um_pixel(mg), dilatar_um_pixel(mv)
    d = {
        "tolerancia_rgb": int(tolerancia),
        "dimensoes": [int(mg.shape[1]), int(mg.shape[0])],
        "pixels_efeito_gl": qtd_gl,
        "pixels_efeito_vk": qtd_vk,
        "pixels_intersecao": qtd_inter,
        "pixels_uniao": qtd_uniao,
        "pixels_so_gl": int((mg & ~mv).sum()),
        "pixels_so_vk": int((mv & ~mg).sum()),
        "iou_localizacao_efeito": qtd_inter / qtd_uniao if qtd_uniao else 1.0,
        "fracao_pixels_gl_a_ate_1px_de_vk":
            float((mg & viz_vk).sum()) / qtd_gl if qtd_gl else 1.0,
        "fracao_pixels_vk_a_ate_1px_de_gl":
            float((mv & viz_gl).sum()) / qtd_vk if qtd_vk else 1.0,
        "nao_homologado": True,
    }
    return d, mg, mv


def criar_mapa(mg, mv):
    if mg.shape != mv.shape:
        raise ValueError("Máscaras não alinhadas")
    img = np.zeros((*mg.shape, 3), dtype=np.uint8)
    img[mg & ~mv] = (255, 75, 75)   # somente OpenGL
    img[mv & ~mg] = (35, 185, 240)  # somente Vulkan
    img[mg & mv] = (255, 255, 255)  # interseção
    return img


def ler_captura(controle):
    # Pillow é dependência somente de diagnóstico na CI, não do produto.
    from PIL import Image
    caminho = Path(controle["arquivo_rgb"])
    arquivo = caminho.read_bytes()
    if hashlib.sha256(arquivo).hexdigest() != controle["sha256_png"]:
        raise ValueError("Hash PNG inválido: " + str(caminho))
    with Image.open(caminho) as imagem:
        if imagem.mode != "RGB":
            raise ValueError("PNG da captura não está em RGB")
        rgb = np.ascontiguousarray(np.asarray(imagem))
    if hashlib.sha256(rgb.tobytes()).hexdigest() != controle["sha256_rgb"]:
        raise ValueError("Hash de pixels RGB inválido: " + str(caminho))
    return rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--pareamento", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    args = parser.parse_args()
    gl = json.loads(args.opengl.read_text(encoding="utf-8"))
    vk = json.loads(args.vulkan.read_text(encoding="utf-8"))
    pareado = json.loads(args.pareamento.read_text(encoding="utf-8"))
    doc = {
        "tipo": "MAPA_ESPACIAL_EFEITO_A2C_RGB",
        "nao_homologado": True,
        "base": "diff RGB intrabackend entre 4x OFF e 4x ON",
        "legenda": {"vermelho": "so_gl", "ciano": "so_vulkan",
                    "branco": "ambos", "preto": "nenhum"},
        "estado": "NAO_TESTAVEL_OPENGL_4X",
    }
    if pareado["estado"] == "CONTROLES_RGB_4X_EM_AMBOS_BACKENDS":
        entradas = [
            ler_captura(m["controles"][nome])
            for m in (gl, vk)
            for nome in ("4x_sem_a2c", "4x_com_a2c")
        ]
        metrica, mg, mv = analisar_efeitos(*entradas)
        doc.update(metrica)
        doc["decomposicao"] = decompor_efeito_a2c(*entradas)
        doc["estado"] = "MEDIDO_SEM_HOMOLOGACAO"
        from PIL import Image
        args.png.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(criar_mapa(mg, mv), mode="RGB").save(args.png)
        doc["arquivo_mapa_png"] = str(args.png)
        doc["sha256_mapa_png"] = hashlib.sha256(args.png.read_bytes()).hexdigest()
        if pareado.get("isolamento_estados", {}).get("estado") != (
            "CONTROLES_INTERMEDIARIOS_VALIDOS"
        ):
            raise ValueError("Estados controlados de blend/Z/A2C não validados")
        # Mesmo blend OFF e escrita Z ON em ambos os lados: a única
        # mudança INTENCIONAL é habilitar sample alpha-to-coverage.
        entradas_isoladas = [
            ler_captura(m["controles"][nome])
            for m in (gl, vk)
            for nome in ("4x_sem_a2c_sem_blend_com_z", "4x_com_a2c")
        ]
        metrica_isolada, mascara_gl, mascara_vk = analisar_efeitos(
            *entradas_isoladas
        )
        isolado_png = args.png.with_name(args.png.stem + "-isolado.png")
        Image.fromarray(criar_mapa(mascara_gl, mascara_vk), mode="RGB").save(
            isolado_png
        )
        doc["isolamento_a2c_4x"] = {
            **metrica_isolada,
            "tipo": "COBERTURA_A2C_COM_BLEND_DESLIGADO_E_Z_LIGADO",
            "contraste": "4x_sem_a2c_sem_blend_com_z vs 4x_com_a2c",
            "decomposicao": decompor_efeito_a2c(*entradas_isoladas),
            "arquivo_mapa_png": str(isolado_png),
            "sha256_mapa_png": hashlib.sha256(isolado_png.read_bytes()).hexdigest(),
            "nao_homologado": True,
        }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
