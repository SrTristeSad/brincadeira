#!/usr/bin/env python3
"""Importa uma cópia independente do MakeHuman para makehumano/codigo/."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

ORIGEM = "https://github.com/makehumancommunity/makehuman.git"
PASTA = Path(__file__).resolve().parent
DESTINO = PASTA / "codigo"


def importar(atualizar=False):
    if shutil.which("git") is None:
        raise RuntimeError("Git não encontrado. Instale o Git e tente novamente.")
    if DESTINO.exists() and not atualizar:
        raise RuntimeError(
            "A pasta codigo/ já existe. Não vou sobrescrever seu trabalho. "
            "Use --atualizar para guardar uma cópia anterior e importar novamente."
        )
    with tempfile.TemporaryDirectory(prefix=".importacao-", dir=PASTA) as temporario:
        temporario = Path(temporario)
        clone = temporario / "repositorio"
        # Os assets distribuídos via Git LFS podem ser baixados separadamente.
        ambiente = os.environ.copy()
        ambiente["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "master", ORIGEM, str(clone)],
            check=True,
            env=ambiente,
        )
        revisao = subprocess.check_output(
            ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
        ).strip()
        preparada = temporario / "codigo-preparado"
        shutil.copytree(clone, preparada, ignore=shutil.ignore_patterns(".git"))
        (preparada / ".makehumano-origem.txt").write_text(
            f"Repositório: {ORIGEM}\nCommit: {revisao}\n",
            encoding="utf-8",
        )
        backup = None
        if DESTINO.exists():
            sufixo = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = PASTA / f"codigo-backup-{sufixo}"
            if backup.exists():
                raise RuntimeError(f"Backup já existe: {backup}")
            DESTINO.rename(backup)
        try:
            preparada.rename(DESTINO)
        except OSError:
            if backup is not None:
                backup.rename(DESTINO)
            raise
    print(f"MakeHuman importado para: {DESTINO}")
    print(f"Revisão original: {revisao}")
    if backup is not None:
        print(f"Cópia anterior preservada em: {backup}")
    print("Importação não é modernização. Execute: python diagnostico.py")
    print("Veja codigo/README.md para obter assets e instalar dependências.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--atualizar",
        action="store_true",
        help="Importar novamente, preservando a pasta anterior como backup.",
    )
    args = parser.parse_args()
    try:
        importar(atualizar=args.atualizar)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
