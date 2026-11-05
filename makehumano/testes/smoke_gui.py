#!/usr/bin/env python3
"""Teste de inicialização real do MakeHuman em servidor X virtual (CI Linux).

Este teste NÃO verifica a aparência da janela ou a correção dos shaders.
Verifica se o carregamento da GUI, dos plugins e dos morph targets terminou.
"""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "executar.py"
TIMEOUT_SECONDS = 90


def main():
    if not os.environ.get("DISPLAY"):
        print("DISPLAY não definido. Execute com xvfb-run ou em desktop X11.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="makehumano-gui-") as pasta:
        base = Path(pasta)
        marker = base / "gui-ready"
        marcador_vulkan = base / "vulkan-frame"
        piloto_vulkan = os.environ.get("MAKEHUMANO_VULKAN_PILOT") == "1"
        logfile = base / "startup.log"
        home = base / "home"
        home.mkdir()
        ambiente = os.environ.copy()
        ambiente["HOME"] = str(home)
        ambiente["XDG_CONFIG_HOME"] = str(home / ".config")
        ambiente["MAKEHUMANO_SMOKE_READY_FILE"] = str(marker)
        if piloto_vulkan:
            ambiente["MAKEHUMANO_VULKAN_FRAME_FILE"] = str(marcador_vulkan)
            ambiente["WGPU_BACKEND_TYPE"] = "Vulkan"
        ambiente["LIBGL_ALWAYS_SOFTWARE"] = "1"
        ambiente["QT_X11_NO_MITSHM"] = "1"

        print(f"Iniciando GUI: {APP}", flush=True)
        with logfile.open("wb") as log:
            processo = subprocess.Popen(
                [sys.executable, "-u", str(APP), "--noshaders"],
                cwd=ROOT,
                env=ambiente,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            iniciou = False
            try:
                # O piloto Vulkan usa menos tempo na CI para identificar
                # falha no primeiro quadro rapidamente, sem atrasar a
                # verificação de regressão do caminho original.
                limite = time.monotonic() + (
                    45 if piloto_vulkan else TIMEOUT_SECONDS
                )
                while time.monotonic() < limite:
                    gui_pronta = (
                        marker.is_file()
                        and marker.read_text(encoding="utf-8").startswith("ready")
                    )
                    quadro_vulkan = (
                        marcador_vulkan.is_file()
                        and marcador_vulkan.read_text(encoding="utf-8").startswith(
                            "vulkan-makehuman-original:"
                        )
                    )
                    if gui_pronta and (not piloto_vulkan or quadro_vulkan):
                        # Se a aplicação saiu imediatamente após iniciar, não considerar sucesso.
                        time.sleep(1)
                        iniciou = processo.poll() is None
                        break
                    if processo.poll() is not None:
                        break
                    time.sleep(0.5)
            finally:
                if processo.poll() is None:
                    processo.terminate()
                    try:
                        processo.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        processo.kill()
                        processo.wait()

        log_text = logfile.read_text(encoding="utf-8", errors="replace")
        print("--- LOG DE INICIALIZAÇÃO (últimos 15 mil caracteres) ---")
        print(log_text[-15000:])
        print("--- FIM DO LOG ---")

        if iniciou and piloto_vulkan:
            # Um frame parcial não equivale à viewport renderizada.
            # Exigir ausência de erros do RenderCanvas no processo.
            erros_graficos = (
                "Draw error",
                "Traceback (most recent call last):",
                "GPUValidationError",
                "WGPUValidationError",
            )
            if any(erro in log_text for erro in erros_graficos):
                print(
                    "FALHA: a viewport Vulkan gerou erros no log da GUI.",
                    file=sys.stderr,
                )
                iniciou = False

        if iniciou:
            print(
                "SUCESSO: GUI original carregada"
                + (" com quadro Vulkan original" if piloto_vulkan else "")
                + "."
            )
            return 0
        print(
            f"FALHA: GUI não terminou a inicialização em {TIMEOUT_SECONDS}s "
            f"(código de saída: {processo.returncode}).",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
