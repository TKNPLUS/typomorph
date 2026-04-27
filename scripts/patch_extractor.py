"""
patch_extractor.py
==================
Extract local patches from SDF (.npy) files and save them as a feature matrix
for downstream clustering (patch_kmeans.py).

Two sampling strategies are supported and can be combined:

border
    Patches whose centre lies within *border_margin* pixels of the SDF = 0
    iso-line (i.e. the glyph outline).  These patches capture the structural
    features of strokes and radicals.

random
    Uniformly random patches sampled from each SDF.

Each extracted patch is resized to *patch_size × patch_size* and flattened
into a 1-D feature vector.  All patches, their grid positions, and the stem of
the source file are saved together in a single compressed NumPy archive.

Distance convention (inherited from make_sdf.py)
-------------------------------------------------
  * **Negative** values → inside (ink / glyph interior)
  * **Positive** values → outside (background)
  * **0**               → glyph outline

Usage
-----
    python scripts/patch_extractor.py \\
        --sdf  out/sdf \\
        --out  out/patches/patches.npz

    # custom patch size, more border patches, add random patches
    python scripts/patch_extractor.py \\
        --sdf  out/sdf \\
        --out  out/patches/patches.npz \\
        --patch-size 64 \\
        --border-patches 20 \\
        --random-patches 5 \\
        --border-margin 8

Arguments
---------
--sdf               Directory containing .npy SDF files (e.g. out/sdf).
--out               Output .npz path for the feature matrix.
--list              Optional character list .txt to restrict which files are
                    processed and to control ordering.
--patch-size        Edge length of each square patch in pixels (default: 64).
--border-patches    Max number of border patches per character (default: 20).
--random-patches    Number of random patches per character (default: 0).
--border-margin     A patch is "border" when the SDF absolute value at its
                    centre is below this threshold in pixels (default: 8).
--seed              Random seed for reproducibility (default: 42).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import zoom


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sdf(path: Path) -> np.ndarray:
    arr = np.load(path)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2-D array, got shape {arr.shape} in {path}")
    return arr.astype(np.float32)


def _read_char_list(list_path: Path) -> list[str]:
    """Return characters from a one-char-per-line text file."""
    chars = []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            chars.append(stripped[0])
    return chars


def _resize_patch(patch: np.ndarray, target: int) -> np.ndarray:
    """Resize a 2-D patch to (target, target) using zoom."""
    if patch.shape == (target, target):
        return patch
    zy = target / patch.shape[0]
    zx = target / patch.shape[1]
    return zoom(patch, (zy, zx), order=1).astype(np.float32)


def _extract_patches_from_sdf(
    sdf: np.ndarray,
    patch_size: int,
    n_border: int,
    n_random: int,
    border_margin: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract patches from a single SDF array.

    Returns
    -------
    patches : (N, patch_size, patch_size) float32
    positions : (N, 2) int32  – (row, col) of the patch top-left corner
    """
    H, W = sdf.shape
    half = patch_size // 2

    # Valid centre range (so patch stays within the image)
    row_min, row_max = half, H - half - 1
    col_min, col_max = half, W - half - 1

    if row_max <= row_min or col_max <= col_min:
        return np.empty((0, patch_size, patch_size), dtype=np.float32), np.empty((0, 2), dtype=np.int32)

    collected_patches: list[np.ndarray] = []
    collected_pos: list[tuple[int, int]] = []

    # ---- Border patches ------------------------------------------------
    if n_border > 0:
        # Centre coordinates where |SDF| < border_margin
        rows, cols = np.where(
            (np.abs(sdf) < border_margin)
            & (np.arange(H)[:, None] >= row_min)
            & (np.arange(H)[:, None] <= row_max)
            & (np.arange(W)[None, :] >= col_min)
            & (np.arange(W)[None, :] <= col_max)
        )

        if len(rows) > 0:
            n_pick = min(n_border, len(rows))
            idx = rng.choice(len(rows), size=n_pick, replace=False)
            for i in idx:
                r, c = int(rows[i]), int(cols[i])
                r0, c0 = r - half, c - half
                patch = sdf[r0:r0 + patch_size, c0:c0 + patch_size]
                collected_patches.append(_resize_patch(patch, patch_size))
                collected_pos.append((r0, c0))

    # ---- Random patches ------------------------------------------------
    if n_random > 0:
        for _ in range(n_random):
            r0 = int(rng.integers(row_min - half, row_max - half + 1))
            c0 = int(rng.integers(col_min - half, col_max - half + 1))
            patch = sdf[r0:r0 + patch_size, c0:c0 + patch_size]
            collected_patches.append(_resize_patch(patch, patch_size))
            collected_pos.append((r0, c0))

    if not collected_patches:
        return np.empty((0, patch_size, patch_size), dtype=np.float32), np.empty((0, 2), dtype=np.int32)

    patches_arr = np.stack(collected_patches, axis=0)
    pos_arr = np.array(collected_pos, dtype=np.int32)
    return patches_arr, pos_arr


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_all(
    sdf_dir: Path,
    *,
    char_list: list[str] | None = None,
    patch_size: int = 64,
    n_border: int = 20,
    n_random: int = 0,
    border_margin: float = 8.0,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract patches from all SDF files in *sdf_dir*.

    Returns
    -------
    features : (N, patch_size * patch_size) float32
        Flattened patches.
    positions : (N, 3) int32
        Columns are [file_index, row, col] of each patch's top-left corner.
    sources : list of str
        File stem for each of the M source files (indexed by features[:, 0]).
    """
    if char_list is not None:
        npy_files = []
        for ch in char_list:
            p = sdf_dir / f"U+{ord(ch):04X}.npy"
            if p.exists():
                npy_files.append(p)
    else:
        npy_files = sorted(sdf_dir.glob("*.npy"))

    if not npy_files:
        sys.exit(f"ERROR: No .npy files found in {sdf_dir}")

    rng = np.random.default_rng(seed)

    all_features: list[np.ndarray] = []
    all_positions: list[np.ndarray] = []
    sources: list[str] = [p.stem for p in npy_files]

    try:
        from tqdm import tqdm
        iterable = tqdm(enumerate(npy_files), total=len(npy_files), desc="Patches", unit="char")
    except ImportError:
        iterable = enumerate(npy_files)

    for file_idx, npy_path in iterable:
        try:
            sdf = _load_sdf(npy_path)
        except Exception as exc:
            print(f"WARNING: Could not load {npy_path}: {exc}", file=sys.stderr)
            continue

        patches, pos = _extract_patches_from_sdf(
            sdf, patch_size, n_border, n_random, border_margin, rng
        )

        if patches.shape[0] == 0:
            continue

        n = patches.shape[0]
        feat = patches.reshape(n, -1)
        all_features.append(feat)

        # Store [file_index, row, col]
        file_col = np.full((n, 1), file_idx, dtype=np.int32)
        all_positions.append(np.hstack([file_col, pos]))

    if not all_features:
        sys.exit("ERROR: No patches were extracted.  Check --sdf directory and settings.")

    features = np.concatenate(all_features, axis=0)
    positions = np.concatenate(all_positions, axis=0)

    print(
        f"Extracted {features.shape[0]} patches from {len(npy_files)} characters "
        f"(patch_size={patch_size}, border={n_border}, random={n_random})"
    )

    return features, positions, sources


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract SDF patches and save feature matrix.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sdf", required=True, metavar="DIR",
        help="Directory containing .npy SDF files (e.g. out/sdf).",
    )
    parser.add_argument(
        "--out", required=True, metavar="PATH",
        help="Output .npz path for the feature matrix.",
    )
    parser.add_argument(
        "--list", metavar="FILE",
        help="Optional character list .txt to restrict/order processing.",
    )
    parser.add_argument(
        "--patch-size", type=int, default=64, metavar="PX",
        help="Square patch edge length in pixels (default: 64).",
    )
    parser.add_argument(
        "--border-patches", type=int, default=20, metavar="N",
        help="Max border patches per character (default: 20).",
    )
    parser.add_argument(
        "--random-patches", type=int, default=0, metavar="N",
        help="Random patches per character (default: 0).",
    )
    parser.add_argument(
        "--border-margin", type=float, default=8.0, metavar="PX",
        help=(
            "SDF absolute-value threshold for 'border' classification "
            "(default: 8 px)."
        ),
    )
    parser.add_argument(
        "--seed", type=int, default=42, metavar="N",
        help="Random seed (default: 42).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sdf_dir = Path(args.sdf)
    if not sdf_dir.is_dir():
        sys.exit(f"ERROR: SDF directory not found: {sdf_dir}")

    char_list: list[str] | None = None
    if args.list:
        list_path = Path(args.list)
        if not list_path.exists():
            sys.exit(f"ERROR: List file not found: {list_path}")
        char_list = _read_char_list(list_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    features, positions, sources = extract_all(
        sdf_dir,
        char_list=char_list,
        patch_size=args.patch_size,
        n_border=args.border_patches,
        n_random=args.random_patches,
        border_margin=args.border_margin,
        seed=args.seed,
    )

    np.savez_compressed(
        out_path,
        features=features,
        positions=positions,
        sources=np.array(sources, dtype=object),
        patch_size=np.int32(args.patch_size),
    )
    print(f"Saved: {out_path}  (features={features.shape}, positions={positions.shape})")


if __name__ == "__main__":
    main()
