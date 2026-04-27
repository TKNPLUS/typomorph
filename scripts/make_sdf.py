"""
make_sdf.py
===========
Generate Signed Distance Field (SDF) numpy arrays from rendered PNG images.

For each character in the list a PNG file is read from *png_dir*, the SDF is
computed, and the result is saved to *out_dir* as a float32 .npy file.

Distance convention
-------------------
  * **Positive** values → outside (background / white pixels)
  * **Negative** values → inside (ink / black pixels)
  * Values are clipped to ``[-clip, +clip]`` (default 32 px).

Usage
-----
    python scripts/make_sdf.py \\
        --list lists/joyo.txt \\
        --png  out/png \\
        --out  out/sdf

    # with parallel workers and custom clip radius
    python scripts/make_sdf.py \\
        --list lists/joyo.txt \\
        --png  out/png \\
        --out  out/sdf \\
        --clip 32 \\
        --workers 4 \\
        --skip-existing

Arguments
---------
--list            Path to a text file with one character per line (UTF-8).
                  Lines starting with '#' and blank lines are ignored.
--png             Directory that contains the source PNG files
                  (e.g. out/png).  File names must be U+XXXX.png.
--out             Output directory for .npy SDF files.  Created automatically
                  if it does not exist.
--clip            Distance clip radius in pixels (default: 32).
--workers         Number of parallel worker processes (default: 1 = serial).
--skip-existing   Skip characters whose output .npy file already exists.
--threshold       Binarisation threshold 0-255; pixels *below* this value are
                  treated as ink/inside (default: 128).
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt


# ---------------------------------------------------------------------------
# Core SDF computation
# ---------------------------------------------------------------------------

def png_to_sdf(
    png_path: Path,
    clip: float = 32.0,
    threshold: int = 128,
) -> np.ndarray:
    """Load a greyscale PNG and return a float32 SDF array.

    Parameters
    ----------
    png_path:
        Path to the source PNG (greyscale or convertible to greyscale).
    clip:
        Distance values are clipped to ``[-clip, +clip]``.
    threshold:
        Pixels with value *strictly below* this threshold are treated as
        ink (inside).  Default 128.

    Returns
    -------
    numpy.ndarray
        float32 array of shape ``(H, W)`` with distances in pixels.
        Inside (ink) pixels carry negative values; outside (background)
        pixels carry positive values.
    """
    img = Image.open(png_path).convert("L")
    pixels = np.array(img, dtype=np.uint8)

    # ink_mask: True where pixel is ink (foreground / inside)
    ink_mask = pixels < threshold

    # Distance from each background pixel to the nearest ink pixel
    dist_outside = distance_transform_edt(~ink_mask)

    # Distance from each ink pixel to the nearest background pixel
    dist_inside = distance_transform_edt(ink_mask)

    # SDF: positive outside, negative inside
    sdf = dist_outside.astype(np.float32) - dist_inside.astype(np.float32)

    return np.clip(sdf, -clip, clip)


# ---------------------------------------------------------------------------
# Worker function (must be top-level for multiprocessing pickling)
# ---------------------------------------------------------------------------

def _process_char(
    char: str,
    png_dir: Path,
    out_dir: Path,
    clip: float,
    threshold: int,
    skip_existing: bool,
) -> tuple[str, str]:
    """Process a single character.  Returns ``(char, status)``."""
    cp = ord(char)
    stem = f"U+{cp:04X}"
    png_path = png_dir / f"{stem}.png"
    out_path = out_dir / f"{stem}.npy"

    if skip_existing and out_path.exists():
        return char, "skipped"

    if not png_path.exists():
        return char, "missing_png"

    sdf = png_to_sdf(png_path, clip=clip, threshold=threshold)
    np.save(out_path, sdf)
    return char, "done"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Signed Distance Field .npy files from rendered PNG images."
        )
    )
    parser.add_argument(
        "--list", required=True, metavar="FILE",
        help="Text file with one character per line.",
    )
    parser.add_argument(
        "--png", required=True, metavar="DIR",
        help="Directory containing source PNG files (e.g. out/png).",
    )
    parser.add_argument(
        "--out", required=True, metavar="DIR",
        help="Output directory for .npy SDF files.",
    )
    parser.add_argument(
        "--clip", type=float, default=32.0, metavar="PX",
        help="Distance clip radius in pixels (default: 32).",
    )
    parser.add_argument(
        "--threshold", type=int, default=128, metavar="0-255",
        help=(
            "Binarisation threshold; pixels below this are ink/inside "
            "(default: 128)."
        ),
    )
    parser.add_argument(
        "--workers", type=int, default=1, metavar="N",
        help="Number of parallel worker processes (default: 1 = serial).",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip characters whose output .npy file already exists.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # -- Validate inputs --
    list_path = Path(args.list)
    if not list_path.exists():
        sys.exit(f"ERROR: List file not found: {list_path}")

    png_dir = Path(args.png)
    if not png_dir.is_dir():
        sys.exit(f"ERROR: PNG directory not found: {png_dir}")

    if not (0 <= args.threshold <= 255):
        sys.exit("ERROR: --threshold must be between 0 and 255.")

    if args.workers < 1:
        sys.exit("ERROR: --workers must be at least 1.")

    # -- Load character list --
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

    # -- Set up progress bar (optional) --
    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False

    # -- Process characters --
    done = skipped = missing = 0

    if args.workers == 1:
        # Serial execution
        iterable = chars
        if use_tqdm:
            iterable = tqdm(chars, desc="SDF", unit="char")

        for char in iterable:
            _, status = _process_char(
                char, png_dir, out_dir,
                args.clip, args.threshold, args.skip_existing,
            )
            if status == "done":
                done += 1
            elif status == "skipped":
                skipped += 1
            else:
                missing += 1
                print(
                    f"WARNING: PNG not found for U+{ord(char):04X} ({char!r}), skipped.",
                    file=sys.stderr,
                )
    else:
        # Parallel execution
        futures = {}
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            for char in chars:
                fut = executor.submit(
                    _process_char,
                    char, png_dir, out_dir,
                    args.clip, args.threshold, args.skip_existing,
                )
                futures[fut] = char

            completed_iter = as_completed(futures)
            if use_tqdm:
                completed_iter = tqdm(
                    completed_iter, total=len(futures), desc="SDF", unit="char"
                )

            for fut in completed_iter:
                char = futures[fut]
                try:
                    _, status = fut.result()
                except Exception as exc:
                    print(
                        f"ERROR: Failed to process U+{ord(char):04X} ({char!r}): {exc}",
                        file=sys.stderr,
                    )
                    missing += 1
                    continue

                if status == "done":
                    done += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    missing += 1
                    print(
                        f"WARNING: PNG not found for U+{ord(char):04X} ({char!r}), skipped.",
                        file=sys.stderr,
                    )

    print(
        f"Done. generated={done}, skipped={skipped}, missing_png={missing}, "
        f"total={len(chars)}"
    )


if __name__ == "__main__":
    main()
