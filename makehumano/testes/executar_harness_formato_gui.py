"""Executa GUI ORIGINAL com plugin temporário de medição; nunca instala recurso.

Este harness testa a cena Vulkan REAL da CI, não o par Phong OpenGL original.
Usa ambiente isolado e remove o plugin transitório ao encerrar.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "codigo" / "makehuman" / "makehuman.py"
PLUGINS = RAIZ / "codigo" / "makehuman" / "plugins"
FONTE_PLUGIN = Path(__file__).with_name("harness_plugin_formato_gui.py")
PLUGIN_TEMPORARIO = PLUGINS / "99_diagnostico_formato_ci.py"


def executar(destino, png, logfile, timeout, fonte_plugin=None):
    destino, png, logfile = (Path(x).resolve() for x in (destino, png, logfile))
    fonte = Path(fonte_plugin).resolve() if fonte_plugin else FONTE_PLUGIN
    if fonte.parent != Path(__file__).resolve().parent or not fonte.is_file():
        raise ValueError('Plugin diagnóstico deve existir no diretório testes')
    for arquivo in (destino, png, logfile):
        arquivo.parent.mkdir(parents=True, exist_ok=True)
    if PLUGIN_TEMPORARIO.exists():
        raise FileExistsError(
            "Plugin temporário já existe; não sobrescrever: " + str(PLUGIN_TEMPORARIO)
        )
    if destino.exists():
        raise FileExistsError("Relatório já existe; use um caminho novo: " + str(destino))
    with tempfile.TemporaryDirectory(prefix="makehumano-harness-formato-") as pasta:
        home = Path(pasta) / "home"
        home.mkdir()
        ambiente = os.environ.copy()
        ambiente.update({
            "MH_HOME_LOCATION": str(home),
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "WGPU_BACKEND_TYPE": "Vulkan",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "QT_X11_NO_MITSHM": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "MAKEHUMANO_CONSOLE_LOG": "1",
            "MAKEHUMANO_HARNESS_TESTES_DIR": str(Path(__file__).parent.resolve()),
            "MAKEHUMANO_HARNESS_FORMATO_JSON": str(destino),
            "MAKEHUMANO_HARNESS_FORMATO_PNG": str(png),
        })
        ambiente.pop("MAKEHUMANO_SMOKE_FUNCTIONAL_FILE", None)
        ambiente.pop("MAKEHUMANO_SMOKE_READY_FILE", None)
        processo = None
        shutil.copyfile(fonte, PLUGIN_TEMPORARIO)
        try:
            with logfile.open("wb") as log:
                processo = subprocess.Popen(
                    [sys.executable, "-u", str(APP)],
                    cwd=str(RAIZ),
                    env=ambiente,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                limite = time.monotonic() + timeout
                while time.monotonic() < limite:
                    if destino.is_file():
                        break
                    if processo.poll() is not None:
                        raise RuntimeError(
                            "GUI encerrou antes de produzir o diagnóstico "
                            f"(exit={processo.returncode})"
                        )
                    time.sleep(0.25)
                else:
                    raise TimeoutError(
                        f"Harness não gerou JSON em {timeout}s; consulte {logfile}"
                    )
        finally:
            if processo is not None and processo.poll() is None:
                processo.terminate()
                try:
                    processo.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    processo.kill()
                    processo.wait(timeout=8)
            PLUGIN_TEMPORARIO.unlink(missing_ok=True)
        if not destino.is_file():
            raise RuntimeError("Captura terminou sem relatório JSON")
        relatorio = json.loads(destino.read_text(encoding="utf-8"))
        observadas = relatorio.get("texturas_offscreen_observadas") or []
        valido = (
            relatorio.get("estado") == "OBSERVADO"
            and relatorio.get("captura_concluida_sem_excecao") is True
            and relatorio.get("captura_1024x768_observada") is True
            and any(
                x.get("largura") == 1024 and x.get("altura") == 768
                and x.get("formato_real_da_textura")
                for x in observadas
            )
            and relatorio.get("dimensoes_imagem") == [1024, 768]
            and png.is_file()
        )
        print(json.dumps(relatorio, ensure_ascii=False, indent=2), flush=True)
        if not valido:
            raise RuntimeError(
                "Formato da cena não foi observado de forma válida; "
                f"consulte {destino} e {logfile}"
            )
        print("Harness: textura 1024x768 observada na GUI original.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=100)
    parser.add_argument("--plugin-source", type=Path,
                        help="Plugin de teste efêmero em makehumano/testes")
    args = parser.parse_args()
    executar(args.json, args.png, args.log, args.timeout, args.plugin_source)


if __name__ == "__main__":
    main()
