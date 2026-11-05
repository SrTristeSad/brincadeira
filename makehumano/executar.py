#!/usr/bin/env python3
"""Executa a cópia importada do MakeHuman com o Python atual."""

from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
PASTA_APP = BASE / "codigo" / "makehuman"
ENTRADA = PASTA_APP / "makehuman.py"


def main():
    if not ENTRADA.is_file():
        print("Código-fonte ausente. Execute primeiro: python importar_original.py")
        return 1
    print("Abrindo o MakeHuman original importado (ainda não modernizado)...", flush=True)
    return subprocess.call([sys.executable, str(ENTRADA), *sys.argv[1:]], cwd=PASTA_APP)


if __name__ == "__main__":
    raise SystemExit(main())
