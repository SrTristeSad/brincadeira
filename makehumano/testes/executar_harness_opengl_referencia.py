"""Captura OpenGL do upstream em checkout externo ao MakeHumano.

Runner somente de testes: copia plugin provisório no clone do original,
executa GUI original e limpa o plugin mesmo sob erro.
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


SOURCE = Path(__file__).resolve().with_name("harness_plugin_opengl_referencia.py")


def executar(raiz, python, saida_json, saida_png, logfile, limite):
    raiz = Path(raiz).resolve()
    # Não usar resolve(): bin/python costuma ser symlink para Python global.
    # O caminho dentro do venv precisa ser passado ao subprocesso intacto.
    python = Path(python).absolute()
    saida_json, saida_png, logfile = (
        Path(p).resolve() for p in (saida_json, saida_png, logfile)
    )
    principal = raiz / "makehuman" / "makehuman.py"
    plugin = raiz / "makehuman" / "plugins" / "99_referencia_opengl_ci.py"
    if not principal.is_file() or not python.is_file():
        raise FileNotFoundError("Checkout upstream ou interpretador isolado ausente")
    if plugin.exists():
        raise FileExistsError("Não sobrescrever plugin já existente: " + str(plugin))
    if saida_json.exists():
        raise FileExistsError("Não reutilizar JSON antigo: " + str(saida_json))
    for arquivo in (saida_json, saida_png, logfile):
        arquivo.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="makehumano-ref-opengl-") as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        env = os.environ.copy()
        env.update({
            "MH_HOME_LOCATION": str(home),
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "GALLIUM_DRIVER": "llvmpipe",
            "QT_X11_NO_MITSHM": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "MAKEHUMANO_HARNESS_TESTES_DIR": str(Path(__file__).resolve().parent),
            "MAKEHUMANO_REF_JSON": str(saida_json),
            "MAKEHUMANO_REF_PNG": str(saida_png),
        })
        env.pop("WGPU_BACKEND_TYPE", None)
        process = None
        shutil.copyfile(SOURCE, plugin)
        try:
            with logfile.open("wb") as log:
                process = subprocess.Popen(
                    [str(python), "-u", str(principal)],
                    cwd=str(principal.parent),
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                fim = time.monotonic() + limite
                while time.monotonic() < fim:
                    if saida_json.is_file():
                        break
                    if process.poll() is not None:
                        raise RuntimeError(
                            f"Upstream OpenGL encerrou antes do JSON (exit={process.returncode}); "
                            f"ver {logfile}"
                        )
                    time.sleep(0.3)
                else:
                    raise TimeoutError(f"Upstream OpenGL não capturou após {limite}s; ver {logfile}")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)
            plugin.unlink(missing_ok=True)

    registro = json.loads(saida_json.read_text(encoding="utf-8"))
    png_sem_especular = saida_png.with_name(saida_png.stem + "-specular-off.png")
    png_sem_sombras = saida_png.with_name(saida_png.stem + "-shadows-off.png")
    png_so_difusa = saida_png.with_name(saida_png.stem + "-diffuse-only.png")
    png_mascara = saida_png.with_name(saida_png.stem + "-alpha-api.png")
    if (registro.get("estado") != "CAPTURADO"
            or registro.get("dimensoes_imagem") != [1024, 768]
            or registro.get("captura_especular_desligado") is not True
            or registro.get("captura_sombras_desligadas") is not True
            or registro.get("captura_so_difusa") is not True
            or registro.get("captura_mascara_api") is not True
            or not saida_png.is_file()
            or not png_sem_especular.is_file()
            or not png_sem_sombras.is_file()
            or not png_so_difusa.is_file()
            or not png_mascara.is_file()):
        raise RuntimeError(
            "Captura de referência OpenGL não válida: "
            + json.dumps(registro, ensure_ascii=False)[:2000]
            + f"; logs em {logfile}"
        )
    print("MakeHuman OpenGL upstream: imagem Phong 1024x768 capturada.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--png", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args()
    executar(args.repo, args.python, args.json, args.png, args.log, args.timeout)


if __name__ == "__main__":
    main()
