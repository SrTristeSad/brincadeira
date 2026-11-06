"""O portátil deve explicar a ausência de Vulkan e sair, sem janela vazia."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="makehumano-no-vulkan-") as directory:
        base = Path(directory)
        env = os.environ.copy()
        env.pop("MAKEHUMANO_PORTABLE_SELFTEST", None)
        env["MH_HOME_LOCATION"] = str(base)
        env["MAKEHUMANO_VULKAN_LOADER"] = str(base / "runtime-inexistente.dll")
        env["MAKEHUMANO_SMOKE_READY_FILE"] = str(base / "ready")
        env["MAKEHUMANO_PORTABLE_ERROR_LOG"] = str(base / "error.log")
        env["MAKEHUMANO_CONSOLE_LOG"] = "1"
        result = subprocess.run([str(executable)], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=60)
        errors = base / "error.log"
        if result.returncode != 1 or not errors.is_file():
            print(result.stdout.decode("utf-8", errors="replace"))
            raise RuntimeError(f"Runtime ausente não encerrou corretamente: {result.returncode}")
        if "runtime-inexistente.dll" not in errors.read_text(encoding="utf-8"):
            raise RuntimeError("Diagnóstico não identificou o runtime ausente")
    print("Runtime Vulkan ausente: erro legível e saída 1 confirmados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
