"""Métricas reproduzíveis de comparação visual OpenGL original vs Vulkan.

Não gera uma referência fictícia. As duas capturas precisam usar a mesma
resolução, cena, câmera, iluminação e estado do MakeHuman original.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def comparar_pixels(referencia, vulkan, *, tolerancia=3, fracao_maxima=0.01):
    """Compara RGBA uint8, sem redimensionar/alinhar imagens automaticamente."""
    a = np.asarray(referencia)
    b = np.asarray(vulkan)
    if (a.ndim != 3 or a.shape[-1] != 4 or not a.size
            or a.dtype != np.uint8 or b.dtype != np.uint8):
        raise ValueError("A referência exige pixels RGBA uint8 [H,W,4]")
    if a.shape != b.shape:
        raise ValueError(f"Capturas com dimensões diferentes: {a.shape} vs {b.shape}")
    if not 0 <= tolerancia <= 255:
        raise ValueError("Tolerância de canal deve estar entre 0 e 255")
    if not 0 <= fracao_maxima <= 1:
        raise ValueError("Fração máxima deve estar entre 0 e 1")

    diferenca = np.abs(a.astype(np.int16) - b.astype(np.int16))
    fora = np.any(diferenca > tolerancia, axis=2)
    total = int(a.shape[0] * a.shape[1])
    divergentes = int(np.count_nonzero(fora))
    cobertura_a = a[:, :, 3] > 0
    cobertura_b = b[:, :, 3] > 0
    uniao = int(np.count_nonzero(cobertura_a | cobertura_b))
    intersecao = int(np.count_nonzero(cobertura_a & cobertura_b))
    return {
        "largura": int(a.shape[1]),
        "altura": int(a.shape[0]),
        "pixels_total": total,
        "pixels_fora_tolerancia": divergentes,
        "fracao_divergente": float(divergentes / total),
        "erro_medio_rgb": float(diferenca[:, :, :3].mean()),
        "erro_maximo_rgba": int(diferenca.max()),
        "pixels_alfa_diferente": int(np.count_nonzero(diferenca[:, :, 3] > tolerancia)),
        "intersecao_uniao_cobertura_alfa": float(intersecao / uniao) if uniao else 1.0,
        "tolerancia_canal": int(tolerancia),
        "fracao_maxima": float(fracao_maxima),
        "aprovado": bool(divergentes / total <= fracao_maxima),
    }


def salvar_mapa_diferencas(referencia, vulkan, destino):
    """Amplifica a diferença RGB e visualiza alfa no quarto canal."""
    from PyQt5 import QtGui

    a = np.asarray(referencia)
    b = np.asarray(vulkan)
    if a.shape != b.shape or a.ndim != 3 or a.shape[-1] != 4:
        raise ValueError("Mapa de diferenças exige imagens RGBA de mesmo tamanho")
    canais = np.minimum(
        np.abs(a.astype(np.int16) - b.astype(np.int16)) * 4, 255
    ).astype(np.uint8)
    # Salvar alfa como luminosidade evita que as diferenças sejam invisíveis.
    canais[:, :, 3] = 255
    h, w = canais.shape[:2]
    pixels = np.ascontiguousarray(canais)
    imagem = QtGui.QImage(
        pixels.data, w, h, w * 4, QtGui.QImage.Format_RGBA8888
    ).copy()
    if not imagem.save(str(destino)):
        raise OSError("Não foi possível salvar mapa de diferenças: " + str(destino))


def main(argv=None):
    from compare_portable_frames import pixels

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("referencia", type=Path, help="PNG do MakeHuman OpenGL original")
    parser.add_argument("vulkan", type=Path, help="PNG do mesmo cenário em Vulkan")
    parser.add_argument("--tolerancia", type=int, default=3, help="Erro permitido por canal [0,255]")
    parser.add_argument("--fracao-maxima", type=float, default=0.01,
                        help="Fração máxima de pixels divergentes [0,1]")
    parser.add_argument("--json", dest="json_path", type=Path,
                        help="Salvar métricas JSON")
    parser.add_argument("--diferenca", type=Path,
                        help="Salvar PNG ampliado das diferenças")
    args = parser.parse_args(argv)
    a, b = pixels(args.referencia), pixels(args.vulkan)
    resultado = comparar_pixels(
        a, b, tolerancia=args.tolerancia, fracao_maxima=args.fracao_maxima,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if args.json_path:
        args.json_path.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.diferenca:
        salvar_mapa_diferencas(a, b, args.diferenca)
    return 0 if resultado["aprovado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
