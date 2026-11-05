#!/usr/bin/env python3
"""Diagnóstico inicial do código e ambiente de execução do MakeHuman."""

import importlib.metadata
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
CODIGO = BASE / "codigo"
DEPENDENCIAS = ("numpy", "PyQt5", "PyOpenGL")


def examinar_sintaxe(pasta):
    erros = []
    total = 0
    for arquivo in sorted(pasta.rglob("*.py")):
        total += 1
        try:
            # Não importa nem executa o código e não cria arquivos __pycache__.
            compile(arquivo.read_bytes(), str(arquivo), "exec")
        except (SyntaxError, UnicodeError, OSError) as exc:
            erros.append((arquivo.relative_to(pasta), str(exc)))
    return total, erros


def main():
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print("Dependências documentadas pelo projeto original:")
    ausentes = []
    for pacote in DEPENDENCIAS:
        try:
            versao = importlib.metadata.version(pacote)
        except importlib.metadata.PackageNotFoundError:
            ausentes.append(pacote)
            print(f"  {pacote}: não instalado")
        else:
            print(f"  {pacote}: {versao}")
    if ausentes:
        print("Instalação conforme o upstream: python -m pip install -r codigo/requirements.txt")

    entrada = CODIGO / "makehuman" / "makehuman.py"
    if not entrada.is_file():
        print("Código-fonte ainda não importado. Execute: python importar_original.py")
        return 1

    total, erros = examinar_sintaxe(CODIGO)
    print(f"Arquivos Python examinados: {total}")
    print(f"Erros de sintaxe: {len(erros)}")
    for caminho, erro in erros[:20]:
        print(f"  {caminho}: {erro}")
    if len(erros) > 20:
        print(f"  ... mais {len(erros) - 20} erros")

    print("Aviso: verificar sintaxe NÃO prova compatibilidade nem testa a interface 3D.")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
