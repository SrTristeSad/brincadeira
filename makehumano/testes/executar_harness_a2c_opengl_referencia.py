"""Captura A2C 4x da referência OpenGL, em checkout externo descartável.

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


SOURCE = Path(__file__).resolve().with_name("harness_plugin_a2c_opengl_referencia.py")


def executar(raiz, python, saida_json, saida_png, logfile, limite):
    raiz = Path(raiz).resolve()
    # Não usar resolve(): bin/python costuma ser symlink para Python global.
    # O caminho dentro do venv precisa ser passado ao subprocesso intacto.
    python = Path(python).absolute()
    saida_json, saida_png, logfile = (
        Path(p).resolve() for p in (saida_json, saida_png, logfile)
    )
    principal = raiz / "makehuman" / "makehuman.py"
    plugin = raiz / "makehuman" / "plugins" / "99_referencia_a2c_ci.py"
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
                    [str(python), "-u", str(principal), "--multisampling"],
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
    if (registro.get("estado") != "CAPTURADO"
            or registro.get("dimensoes_imagem") != [1024, 768]
            or registro.get("tipo_experimento") != "A2C_MSAA_RGB_REFERENCIA_GL_SEM_HOMOLOGACAO"
            or registro.get("suporte_msaa", {}).get("cli_multisampling") is not True
            or registro.get("resultado_a2c") not in (
                "EXECUTADO_COM_MSAA_4X", "NAO_TESTAVEL_MSAA_4X"
            )
            or "1x_sem_a2c" not in registro.get("controles", {})
            or not saida_png.is_file()):
        raise RuntimeError(
            "Diagnóstico A2C OpenGL inválido: "
            + json.dumps(registro, ensure_ascii=False)[:2000]
            + f"; logs em {logfile}"
        )
    if registro["resultado_a2c"] == "EXECUTADO_COM_MSAA_4X":
        from diagnosticar_a2c_msaa import validar_controles
        controles = registro["controles"]
        # Exige amostras do FBO REAL, além da flag CLI.
        validar_controles(controles)
        for nome in ("4x_sem_a2c", "4x_com_a2c", "4x_inelegivel"):
            arq = saida_png.with_name(saida_png.stem + "-" + nome + ".png")
            if not arq.is_file() or controles[nome]["amostras_fbo_observadas"] != 4:
                raise RuntimeError("A2C OpenGL sem PNG/FBO 4x real: " + nome)
        if not controles["4x_com_a2c"]["rastros_gl"]["ativacoes_a2c"]:
            raise RuntimeError("OpenGL não habilitou GL_SAMPLE_ALPHA_TO_COVERAGE")
        print("Referência OpenGL: MSAA 4x e A2C registrados.", flush=True)
    else:
        print("Referência OpenGL: NÃO TESTÁVEL com MSAA 4x; evidência preservada.", flush=True)


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
