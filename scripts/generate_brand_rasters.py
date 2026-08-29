"""Regenerate raster brand assets from the canonical SVG masters.

This is a maintainer utility, not a runtime dependency. Install CairoSVG and
Pillow in the environment before running it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

try:
    import cairosvg
    from PIL import Image
except ImportError as exc:  # pragma: no cover - maintainer environment guard
    raise SystemExit(
        "brand raster generation requires CairoSVG and Pillow: "
        "python -m pip install cairosvg pillow"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
DESKTOP = ROOT / "desktop" / "src-tauri" / "icons"


def _render(svg_name: str, output: Path, size: int) -> None:
    cairosvg.svg2png(
        bytestring=(BRAND / svg_name).read_bytes(),
        write_to=str(output),
        output_width=size,
        output_height=size,
    )


def main() -> int:
    _render("lifetxt-app-icon.svg", BRAND / "lifetxt-app-icon-1024.png", 1024)
    _render("lifetxt-favicon.svg", BRAND / "favicon-32.png", 32)
    _render("lifetxt-app-icon.svg", BRAND / "apple-touch-icon-180.png", 180)
    _render("lifetxt-app-icon.svg", BRAND / "pwa-icon-192.png", 192)
    _render("lifetxt-app-icon.svg", BRAND / "pwa-icon-512.png", 512)
    _render("lifetxt-maskable-icon.svg", BRAND / "pwa-maskable-512.png", 512)

    DESKTOP.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BRAND / "pwa-icon-512.png", DESKTOP / "icon.png")

    source = Image.open(BRAND / "lifetxt-app-icon-1024.png").convert("RGBA")
    source.save(
        DESKTOP / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
