"""
render_png.py
=============
Render kanji characters from a list file to normalised 256x256 PNG images.

Usage
-----
    python scripts/render_png.py \
        --list lists/joyo.txt \
        --out  out/png \
        --font "Noto Sans CJK JP"

Arguments
---------
--list            Path to a text file with one character per line (UTF-8).
                  Lines starting with '#' and blank lines are ignored.
--out             Output directory. Created automatically if it does not exist.
--font            Font family name resolved via fontconfig (fc-match).
                  Example: "Noto Sans CJK JP"
--size            Canvas size in pixels (default: 256).
--margin          Margin ratio, e.g. 0.1 means 10% padding on each side
                  (default: 0.10).
--skip-existing   Skip characters whose output file already exists.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# fontconfig helpers
# ---------------------------------------------------------------------------

def _fc_match(family: str) -> Path:
    """Return the file path of the best font match for *family* via fc-match.

    Raises SystemExit with an informative message when the font cannot be
    resolved or fontconfig is not available.
    """
    try:
        result = subprocess.run(
            ["fc-match", "--format=%{file}", family],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit(
            "ERROR: fc-match not found. "
            "Please install fontconfig (apt install fontconfig) or run inside Docker."
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f"ERROR: fc-match failed: {exc.stderr.strip()}")

    font_file = result.stdout.strip()
    if not font_file:
        sys.exit(f"ERROR: fc-match returned an empty path for font '{family}'.")

    path = Path(font_file)
    if not path.exists():
        sys.exit(f"ERROR: Resolved font path does not exist: {font_file}")

    # Verify the resolved font actually matches the requested family (best effort)
    try:
        check = subprocess.run(
            ["fc-match", "--format=%{family}", family],
            capture_output=True,
            text=True,
            check=True,
        )
        resolved_family = check.stdout.strip().lower()
        requested_family = family.lower()
        if requested_family not in resolved_family and resolved_family not in requested_family:
            print(
                f"WARNING: Requested font family '{family}' resolved to '{resolved_family}'. "
                "Rendering may look unexpected. "
                "Run 'fc-list | grep -i noto' to check available fonts.",
                file=sys.stderr,
            )
    except Exception:
        pass  # family check is best-effort only

    return path


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_char(
    char: str,
    font: ImageFont.FreeTypeFont,
    size: int,
    margin: float,
) -> Image.Image:
    """Render *char* onto a white canvas of *size*×*size* pixels.

    The glyph is centred and scaled so that its bounding box fills the
    canvas minus *margin* on each side (margin is given as a fraction of
    *size*).
    """
    # -- Measure glyph bounding box on a temporary canvas --
    tmp = Image.new("L", (size * 4, size * 4), color=255)
    draw_tmp = ImageDraw.Draw(tmp)

    # Pillow >= 9.2 returns (left, top, right, bottom) from getbbox
    draw_tmp.text((size * 2, size * 2), char, font=font, fill=0, anchor="mm")
    bbox = tmp.getbbox()  # tight bbox of non-white pixels

    if bbox is None:
        # Blank glyph (space, etc.) – return white canvas
        return Image.new("L", (size, size), color=255)

    glyph_w = bbox[2] - bbox[0]
    glyph_h = bbox[3] - bbox[1]

    if glyph_w == 0 or glyph_h == 0:
        return Image.new("L", (size, size), color=255)

    # -- Compute scale so glyph fits inside (1 - 2*margin) * size --
    target = size * (1.0 - 2.0 * margin)
    scale = target / max(glyph_w, glyph_h)

    # Scaled glyph dimensions
    new_w = int(glyph_w * scale)
    new_h = int(glyph_h * scale)

    # Crop exactly the glyph from the temporary canvas
    glyph_img = tmp.crop(bbox)
    glyph_img = glyph_img.resize((new_w, new_h), Image.LANCZOS)

    # -- Paste onto centred white canvas --
    canvas = Image.new("L", (size, size), color=255)
    paste_x = (size - new_w) // 2
    paste_y = (size - new_h) // 2
    canvas.paste(glyph_img, (paste_x, paste_y))
    return canvas


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render kanji characters to normalised 256×256 PNG images."
    )
    parser.add_argument("--list", required=True, metavar="FILE",
                        help="Text file with one character per line.")
    parser.add_argument("--out", required=True, metavar="DIR",
                        help="Output directory for PNG files.")
    parser.add_argument("--font", required=True, metavar="FAMILY",
                        help='Font family name for fc-match, e.g. "Noto Sans CJK JP".')
    parser.add_argument("--size", type=int, default=256, metavar="PX",
                        help="Canvas size in pixels (default: 256).")
    parser.add_argument("--margin", type=float, default=0.10, metavar="RATIO",
                        help="Margin ratio on each side (default: 0.10).")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip characters whose output PNG already exists.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # -- Resolve font via fontconfig --
    font_path = _fc_match(args.font)
    print(f"Using font: {font_path}")

    # Load font at a large size for the temporary canvas; rendering uses
    # explicit scaling so the initial size just needs to be big enough.
    try:
        pil_font = ImageFont.truetype(str(font_path), size=args.size * 2)
    except Exception as exc:
        sys.exit(f"ERROR: Failed to load font '{font_path}': {exc}")

    # -- Load character list --
    list_path = Path(args.list)
    if not list_path.exists():
        sys.exit(f"ERROR: List file not found: {list_path}")

    chars = [
        line.strip()
        for line in list_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not chars:
        sys.exit(f"ERROR: No characters found in {list_path}")

    # -- Prepare output directory --
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # -- Render --
    try:
        from tqdm import tqdm
        iterable = tqdm(chars, desc="Rendering", unit="char")
    except ImportError:
        iterable = chars

    skipped = 0
    rendered = 0
    for char in iterable:
        cp = ord(char)
        filename = f"U+{cp:04X}.png"
        out_path = out_dir / filename

        if args.skip_existing and out_path.exists():
            skipped += 1
            continue

        img = render_char(char, pil_font, args.size, args.margin)
        img.save(out_path)
        rendered += 1

    print(f"Done. rendered={rendered}, skipped={skipped}, total={len(chars)}")


if __name__ == "__main__":
    main()
