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
        marcador_picking = base / "vulkan-picking"
        marcador_offscreen = base / "vulkan-offscreen"
        marcador_render = base / "vulkan-render"
        marcador_skin = base / "vulkan-skin"
        marcador_xray = base / "vulkan-xray"
        marcador_litsphere = base / "vulkan-litsphere"
        marcador_estilos = base / "vulkan-phong-toon"
        marcador_normalmap = base / "vulkan-normalmap"
        marcador_recorte = base / "vulkan-recorte"
        marcador_skin_shader = base / "vulkan-skin-shader"
        logfile = base / "startup.log"
        home = base / "home"
        home.mkdir()
        ambiente = os.environ.copy()
        ambiente["HOME"] = str(home)
        ambiente["XDG_CONFIG_HOME"] = str(home / ".config")
        ambiente["MAKEHUMANO_SMOKE_READY_FILE"] = str(marker)
        # Vulkan é o único backend; estes marcadores são sempre obrigatórios.
        ambiente.pop("MAKEHUMANO_VULKAN_PILOT", None)
        ambiente["MAKEHUMANO_VULKAN_FRAME_FILE"] = str(marcador_vulkan)
        ambiente["MAKEHUMANO_VULKAN_PICK_FILE"] = str(marcador_picking)
        ambiente["MAKEHUMANO_VULKAN_OFFSCREEN_FILE"] = str(marcador_offscreen)
        ambiente["MAKEHUMANO_VULKAN_RENDER_FILE"] = str(marcador_render)
        ambiente["MAKEHUMANO_VULKAN_SKIN_FILE"] = str(marcador_skin)
        ambiente["MAKEHUMANO_VULKAN_XRAY_FILE"] = str(marcador_xray)
        ambiente["MAKEHUMANO_VULKAN_LITSPHERE_FILE"] = str(marcador_litsphere)
        ambiente["MAKEHUMANO_VULKAN_ESTILOS_FILE"] = str(marcador_estilos)
        ambiente["MAKEHUMANO_VULKAN_NORMALMAP_FILE"] = str(marcador_normalmap)
        ambiente["MAKEHUMANO_VULKAN_RECORTE_FILE"] = str(marcador_recorte)
        ambiente["MAKEHUMANO_VULKAN_SKIN_SHADER_FILE"] = str(marcador_skin_shader)
        ambiente["WGPU_BACKEND_TYPE"] = "Vulkan"
        ambiente["LIBGL_ALWAYS_SOFTWARE"] = "1"
        ambiente["QT_X11_NO_MITSHM"] = "1"

        print(f"Iniciando GUI: {APP}", flush=True)
        with logfile.open("wb") as log:
            processo = subprocess.Popen(
                [sys.executable, "-u", str(APP)],
                cwd=ROOT,
                env=ambiente,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            iniciou = False
            try:
                limite = time.monotonic() + TIMEOUT_SECONDS
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
                    picking_valido = (
                        marcador_picking.is_file()
                        and len(marcador_picking.read_text(
                            encoding="utf-8"
                        ).strip().split(",")) == 3
                    )
                    framebuffer_valido = (
                        marcador_offscreen.is_file()
                        and marcador_offscreen.read_text(
                            encoding="utf-8"
                        ).strip() == "vulkan-offscreen:320x240"
                    )
                    render_valido = (
                        marcador_render.is_file()
                        and marcador_render.read_text(encoding="utf-8").startswith(
                            "vulkan-render:160x120:"
                        )
                    )
                    skin_valido = (
                        marcador_skin.is_file()
                        and marcador_skin.read_text(encoding="utf-8").strip()
                        == "vulkan-skin:96x96"
                    )
                    xray_valido = (
                        marcador_xray.is_file()
                        and marcador_xray.read_text(encoding="utf-8").startswith(
                            "vulkan-xray:160x120:"
                        )
                    )
                    litsphere_valido = (
                        marcador_litsphere.is_file()
                        and marcador_litsphere.read_text(
                            encoding="utf-8",
                        ).startswith("vulkan-litsphere:160x120:")
                    )
                    estilos_validos = (
                        marcador_estilos.is_file()
                        and marcador_estilos.read_text(
                            encoding="utf-8"
                        ).startswith("vulkan-phong-toon:160x120:")
                    )
                    normalmap_valido = (
                        marcador_normalmap.is_file()
                        and marcador_normalmap.read_text(
                            encoding="utf-8"
                        ).startswith("vulkan-normalmap:160x120:")
                    )
                    recorte_valido = (
                        marcador_recorte.is_file()
                        and marcador_recorte.read_text(
                            encoding="utf-8"
                        ).startswith("vulkan-recorte:160x120:")
                    )
                    skin_shader_valido = (
                        marcador_skin_shader.is_file()
                        and marcador_skin_shader.read_text(
                            encoding="utf-8"
                        ).startswith("vulkan-skin-shader:160x120:")
                    )
                    if (
                        gui_pronta and quadro_vulkan and picking_valido
                        and framebuffer_valido and render_valido and skin_valido
                        and xray_valido and litsphere_valido
                        and estilos_validos and normalmap_valido
                        and skin_shader_valido and recorte_valido
                    ):
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

        if iniciou:
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
                "SUCESSO: GUI original carregada com quadro, picking e"
                " renderização Vulkan."
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
