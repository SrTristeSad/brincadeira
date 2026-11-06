"""Carregar o runtime Vulkan no Windows antes de inicializar wgpu-native."""
import os
from pathlib import Path
import sys

_loader = None
_dll_directory = None


def preparar_runtime_vulkan():
    global _loader, _dll_directory
    if sys.platform != "win32" or _loader is not None:
        return
    import ctypes
    # A CI pode selecionar explicitamente seu loader de software. No desktop,
    # usar o runtime instalado pelo driver de vídeo, sem distribuir drivers.
    path = Path(os.environ.get("MAKEHUMANO_VULKAN_LOADER") or
                Path(os.environ["SystemRoot"]) / "System32" / "vulkan-1.dll")
    if not path.is_absolute():
        raise RuntimeError("O caminho do loader Vulkan deve ser absoluto")
    try:
        # Python >=3.8 e PyInstaller restringem a busca de dependências DLL.
        # Manter o diretório e o handle vivos também durante a carga via ash.
        _dll_directory = os.add_dll_directory(str(path.parent))
        _loader = ctypes.WinDLL(str(path))
    except OSError as exc:
        raise RuntimeError(
            f"Não foi possível carregar o runtime Vulkan {path}: {exc}. "
            "Instale/atualize o driver Vulkan da sua placa de vídeo."
        ) from exc
    print(f"MAKEHUMANO_VULKAN: runtime carregado de {path}", flush=True)
