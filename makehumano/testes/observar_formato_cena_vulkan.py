"""Espia somente a captura do harness isolado, sem mudar o renderer Vulkan.

Importar no plugin externo 99_captura_referencia.py, após criar a CenaVulkan.
Não incluir este observador no caminho normal do MakeHumano.
"""

from contextlib import contextmanager
import json
from pathlib import Path


@contextmanager
def observar_captura_offscreen(cena, destino_json):
    """Registra formatos reais das texturas produzidas por framebuffer_offscreen.

    Envolve apenas o período da captura já feita pelo harness, encaminhando
    todos os argumentos ao método original sem modificar o retorno. O método
    é restaurado mesmo que a captura falhe. Nenhum framebuffer é criado aqui.
    """
    if cena is None:
        raise RuntimeError("CenaVulkan ausente: execute após o primeiro frame")
    if not hasattr(cena, "__dict__"):
        raise TypeError("A cena precisa permitir instrumentação local no harness")

    original = cena.framebuffer_offscreen
    anterior = cena.__dict__.get("framebuffer_offscreen", _AUSENTE)
    preferido = cena.contexto.get_preferred_format(cena.adapter)
    evidencia = {
        "tipo": "DIAGNOSTICO_FORMATO_CENA_REAL",
        "formato_preferido_superficie": str(preferido),
        "formato_cena_inicial": str(cena.formato),
        "captura_concluida_sem_excecao": False,
        "texturas_offscreen_observadas": [],
    }

    def intermediar(*args, **kwargs):
        textura = original(*args, **kwargs)
        largura = args[0] if len(args) > 0 else kwargs.get("largura")
        altura = args[1] if len(args) > 1 else kwargs.get("altura")
        requisitado = kwargs.get("formato")
        evidencia["texturas_offscreen_observadas"].append({
            "largura": int(largura),
            "altura": int(altura),
            "formato_requisitado": None if requisitado is None else str(requisitado),
            "formato_cena_no_instante": str(cena.formato),
            "formato_real_da_textura": str(textura.format),
        })
        return textura

    cena.framebuffer_offscreen = intermediar
    try:
        yield evidencia
        evidencia["captura_concluida_sem_excecao"] = True
    except BaseException as exc:
        evidencia["erro_da_captura"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if anterior is _AUSENTE:
            del cena.framebuffer_offscreen
        else:
            cena.framebuffer_offscreen = anterior
        evidencia["formato_cena_final"] = str(cena.formato)
        evidencia["observou_captura_offscreen"] = bool(
            evidencia["texturas_offscreen_observadas"]
        )
        destino = Path(destino_json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(evidencia, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


_AUSENTE = object()
