"""Analisar também módulos e plugins carregados por nome pelo MakeHuman.

Copiar os .py para o ZIP permite carregá-los, mas não inclui suas dependências
no Python congelado. Enumerar os módulos sem executá-los durante a build.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "codigo" / "makehuman"
hiddenimports = ["cProfile"]
for directory in ("lib", "core", "shared", "apps", "apps/gui", "plugins"):
    base = root / directory
    for source in sorted(base.rglob("*.py")):
        relative = source.relative_to(base)
        # Pastas sem __init__.py têm seu próprio caminho em --paths.
        if any(not (base.joinpath(*relative.parts[:i]) / "__init__.py").is_file()
               for i in range(1, len(relative.parts))):
            continue
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            hiddenimports.append(".".join(parts))
hiddenimports = sorted(set(hiddenimports))
