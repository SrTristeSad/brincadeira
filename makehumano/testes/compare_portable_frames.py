"""Comparar pixels dos mesmos cenários Vulkan nos fontes e no portátil."""
from pathlib import Path
import sys
import numpy as np
from PyQt5 import QtGui

FRAMES = (
    "xray", "litsphere", "phong", "toon", "skin-red", "skin-blue",
    "normalmap-flat", "normalmap-tilted", "specular-white", "specular-black",
    "transparent-triangles", "transparent-triangles-reversed",
    "viewport-solid", "viewport-wireframe",
    "map-specular-white", "map-specular-black", "map-transparency-none",
    "map-transparency-grey", "map-transparency-clear",
    "light-point", "light-attenuated", "light-spot", "light-spot-away",
    "bump-disabled", "bump-enabled",
    "ao-grey", "ao-black",
    "ao-phong-white", "ao-phong-black",
    "projection-3d", "projection-accumulated",
    "projection-perspective",
    "light-area", "light-area-two", "light-area-phong",
    "msaa-off", "msaa-4x", "alpha-to-coverage", "alpha-blend-msaa",
    "rig-rest", "rig-tpose",
    "shadow-off", "shadow-point", "shadow-area",
    "shadow-cutout", "shadow-opacity", "shadow-layers",
    "uv-map",
    "displacement-off", "displacement-on",
    "projection-original", "projection-displaced", "projection-painted-viewport",
)


def pixels(path):
    image = QtGui.QImage(str(path))
    if image.isNull():
        raise RuntimeError(f"Captura ausente/inválida: {path}")
    image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    raw = image.bits().asstring(image.byteCount())
    return np.frombuffer(raw, np.uint8).reshape(
        image.height(), image.bytesPerLine())[:, :image.width() * 4].reshape(
        image.height(), image.width(), 4)


def compare(source, frozen):
    for frame in FRAMES:
        a = pixels(source / (frame + ".png"))
        b = pixels(frozen / (frame + ".png"))
        if a.shape != b.shape:
            raise RuntimeError(f"{frame}: resoluções diferentes")
        count = int(np.count_nonzero(np.any(a != b, axis=2)))
        print(f"{frame}: {count} pixels diferentes", flush=True)
        if count:
            raise RuntimeError(f"{frame}: fontes e executável produziram imagens diferentes")


def main():
    compare(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"As {len(FRAMES)} capturas Vulkan são idênticas entre fontes e executável.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
