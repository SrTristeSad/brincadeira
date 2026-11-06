"""Separar falha do driver de teste de falha do executável congelado."""
import ctypes
import os
from pathlib import Path

path = Path(os.environ["MAKEHUMANO_VULKAN_LOADER"])
directory = os.add_dll_directory(str(path.parent))
loader = ctypes.WinDLL(str(path))
import wgpu
wgpu.logger.setLevel("DEBUG")
from wgpu.backends.wgpu_native.extras import set_instance_extras
set_instance_extras(backends=("Vulkan",))
adapters = wgpu.gpu.enumerate_adapters_sync()
print([adapter.info for adapter in adapters], flush=True)
if not any("vulkan" in str(adapter.info).lower() for adapter in adapters):
    raise RuntimeError("O driver de teste não oferece adaptador Vulkan")
