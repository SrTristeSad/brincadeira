"""Métricas RGB e validação de controles MSAA/A2C, apenas diagnósticos CI."""
import hashlib
import numpy as np

CONTROLES = {
    "1x_sem_a2c": (1, False),
    "4x_sem_a2c": (4, False),
    "4x_com_a2c": (4, True),
    "4x_inelegivel": (4, False),
}


def validar_rgb(pixels):
    arr = np.asarray(pixels)
    if arr.ndim != 3 or arr.shape[2] != 3 or arr.dtype != np.uint8:
        raise ValueError("A captura A2C precisa ser RGB uint8 HxWx3")
    return np.ascontiguousarray(arr)


def metadados_rgb(pixels):
    arr = validar_rgb(pixels)
    return {
        "dimensoes": [int(arr.shape[1]), int(arr.shape[0])],
        "sha256_rgb": hashlib.sha256(arr.tobytes()).hexdigest(),
    }


def comparar_rgb(a, b, *, tolerancia=8):
    x, y = validar_rgb(a), validar_rgb(b)
    if x.shape != y.shape:
        raise ValueError("Capturas RGB precisam ter a mesma resolução")
    if not 0 <= tolerancia <= 255:
        raise ValueError("Tolerância RGB inválida")
    delta = np.abs(x.astype(np.int16) - y.astype(np.int16))
    pixels = np.any(delta > tolerancia, axis=2)
    return {
        "tolerancia_rgb": int(tolerancia),
        "pixels_divergentes": int(np.count_nonzero(pixels)),
        "fracao_divergente": float(np.mean(pixels)),
        "erro_medio_rgb": float(np.mean(delta)),
        "erro_maximo_rgb": int(np.max(delta)),
        "arrays_identicos": bool(np.array_equal(x, y)),
    }


def validar_controles(registros):
    """Confirma estados registrados; não confunde valores previstos e pipeline observado."""
    if set(registros) != set(CONTROLES):
        raise ValueError("Conjunto de controles MSAA/A2C incompleto")
    for nome, (amostras, a2c) in CONTROLES.items():
        r = registros[nome]
        if r.get("amostras") != amostras or r.get("a2c_elegivel") is not a2c:
            raise ValueError("Controle incorreto: " + nome)
        if r.get("pipeline_a2c_observado") is not a2c:
            raise ValueError("Pipeline não confirmou A2C: " + nome)
        if r.get("captura_rgb") is not True or not r.get("sha256_rgb"):
            raise ValueError("Sem captura real RGB: " + nome)
    return True
