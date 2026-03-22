"""icon-org.png から各種プラットフォーム用アイコンファイルを生成

icon-org.png を更新した際に手動で実行用
  pip install Pillow
  python scripts/generate_icons.py

出力:
  viewer/icon/icon.ico   -- Windows 用 (16/24/32/48/64/128/256px)
  viewer/icon/icon.icns  -- macOS 用 (16/32/48/128/256/512px)
  viewer/icon/icon.png   -- アプリ実行時用 (256x256)
"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "viewer" / "icon"
SRC = ICON_DIR / "icon-org.png"

# Windows ICO に含めるサイズ
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

# macOS ICNS に含めるサイズ
ICNS_SIZES = [16, 32, 48, 128, 256, 512]


def generate():
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        sys.exit(1)

    img = Image.open(SRC).convert("RGBA")
    print(f"Source: {SRC} ({img.width}x{img.height})")

    # --- Windows ICO ---
    ico_path = ICON_DIR / "icon.ico"
    ico_images = [img.resize((s, s), Image.LANCZOS) for s in ICO_SIZES]
    ico_images[-1].save(
        ico_path,
        format="ICO",
        append_images=ico_images[:-1],
    )
    print(f"Generated: {ico_path}")

    # --- macOS ICNS ---
    icns_path = ICON_DIR / "icon.icns"
    icns_images = [img.resize((s, s), Image.LANCZOS) for s in ICNS_SIZES]
    icns_images[-1].save(
        icns_path,
        format="ICNS",
        append_images=icns_images[:-1],
    )
    print(f"Generated: {icns_path}")

    # --- Runtime PNG (256x256) ---
    runtime_png = ICON_DIR / "icon.png"
    img.resize((256, 256), Image.LANCZOS).save(runtime_png, format="PNG")
    print(f"Generated: {runtime_png}")


if __name__ == "__main__":
    generate()
