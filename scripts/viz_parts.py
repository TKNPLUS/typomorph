"""
viz_parts.py
============
Visualise the "parts dictionary" produced by patch_kmeans.py.

Two visualisation modes are available:

gallery (default)
    A grid showing the representative patch for every cluster.  Each cell
    is labelled with the cluster index and the number of patches assigned to
    it.  The patches are rendered as SDF heat-maps (diverging colour map,
    same convention as viz_sdf.py).

heatmap
    For each cluster, a 2-D histogram of where in the original SDF images
    its member patches appear.  All per-cluster maps are arranged in a grid
    so you can see at a glance which "part" tends to appear at which
    position in a character (e.g. left-side radical vs. top component).

Both output files are written as PNG images.

Distance convention (inherited from make_sdf.py / viz_sdf.py)
--------------------------------------------------------------
  * **Negative** values → inside (ink) → blue
  * **Positive** values → outside (background) → red
  * **0**               → glyph outline → white

Usage
-----
    # gallery only (default)
    python scripts/viz_parts.py \\
        --kmeans out/patches/kmeans.npz \\
        --out    out/patches/parts_gallery.png

    # position heatmaps
    python scripts/viz_parts.py \\
        --kmeans  out/patches/kmeans.npz \\
        --out     out/patches/parts_gallery.png \\
        --heatmap out/patches/parts_heatmap.png \\
        --sdf-size 256

    # also pass feature file to enable richer stats
    python scripts/viz_parts.py \\
        --kmeans   out/patches/kmeans.npz \\
        --features out/patches/patches.npz \\
        --out      out/patches/parts_gallery.png \\
        --heatmap  out/patches/parts_heatmap.png

Arguments
---------
--kmeans        Path to the .npz produced by patch_kmeans.py (required).
--features      Path to the .npz produced by patch_extractor.py (optional;
                enables position heatmaps from stored patch positions).
--out           Output path for the parts gallery PNG
                (default: parts_gallery.png next to --kmeans).
--heatmap       Output path for the position heatmap PNG.  Requires
                --features.  Omit to skip heatmap generation.
--sdf-size      Pixel side-length of the original SDF images (default: 256).
                Used to set the extent of the heatmap axes.
--cols          Columns in the gallery grid (default: 8).
--thumb         Thumbnail size in pixels (default: 96).
--cmap          Matplotlib colormap for patch thumbnails (default: RdBu_r).
--hcmap         Matplotlib colormap for heatmaps (default: hot).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_kmeans(path: Path) -> dict:
    data = np.load(path, allow_pickle=True)
    return {k: data[k] for k in data.files}


def _load_features(path: Path) -> dict:
    data = np.load(path, allow_pickle=True)
    return {k: data[k] for k in data.files}


# ---------------------------------------------------------------------------
# Gallery visualisation
# ---------------------------------------------------------------------------

def visualise_gallery(
    kmeans_data: dict,
    *,
    out_path: Path,
    cols: int = 8,
    thumb_px: int = 96,
    cmap: str = "RdBu_r",
) -> None:
    """Save a grid of representative patches, one per cluster."""
    rep_patches = kmeans_data["rep_patches"]           # (k, H, W)
    labels = kmeans_data["labels"]                     # (N,)
    n_clusters = int(kmeans_data["n_clusters"])
    patch_size = int(kmeans_data["patch_size"])

    # Count members per cluster
    counts = np.bincount(labels, minlength=n_clusters)

    rows = (n_clusters + cols - 1) // cols
    dpi = 100
    cell_in = thumb_px / dpi
    fig_w = cols * cell_in
    fig_h = rows * cell_in

    fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h), squeeze=False)

    for ax_row in axes:
        for ax in ax_row:
            ax.axis("off")

    for k_idx in range(n_clusters):
        r, c = divmod(k_idx, cols)
        ax = axes[r][c]
        patch = rep_patches[k_idx]                     # (patch_size, patch_size)
        vmax = float(np.abs(patch).max()) or 1.0
        ax.imshow(
            patch,
            cmap=cmap,
            vmin=-vmax,
            vmax=vmax,
            origin="upper",
            interpolation="nearest",
        )
        ax.contour(patch, levels=[0.0], colors="white", linewidths=0.3)
        label = f"{k_idx}\n({counts[k_idx]})"
        ax.set_title(
            label,
            fontsize=max(2, thumb_px // 12),
            pad=1,
            linespacing=1.1,
        )
        ax.axis("off")

    fig.suptitle(
        f"Parts dictionary  –  {n_clusters} clusters  "
        f"(patch {patch_size}px, Blue=inside / Red=outside)",
        fontsize=max(6, thumb_px // 8),
        y=1.001,
    )
    fig.tight_layout(pad=0.1)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Gallery saved: {out_path}  ({n_clusters} clusters, {rows}×{cols} grid)")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Position heatmap visualisation
# ---------------------------------------------------------------------------

def visualise_heatmaps(
    kmeans_data: dict,
    features_data: dict,
    *,
    out_path: Path,
    sdf_size: int = 256,
    cols: int = 8,
    thumb_px: int = 96,
    hcmap: str = "hot",
) -> None:
    """Save a grid of 2-D position heatmaps, one per cluster.

    Each heatmap shows how often patches from that cluster were found at
    each location in the original SDF image grid.
    """
    labels = kmeans_data["labels"]                     # (N,)
    n_clusters = int(kmeans_data["n_clusters"])
    patch_size = int(kmeans_data["patch_size"])
    positions = features_data["positions"]             # (N, 3): [file_idx, row, col]

    if positions.shape[1] < 3:
        print(
            "WARNING: Position data has unexpected shape; skipping heatmap.",
            file=sys.stderr,
        )
        return

    rows = (n_clusters + cols - 1) // cols
    dpi = 100
    cell_in = thumb_px / dpi
    fig_w = cols * cell_in
    fig_h = rows * cell_in

    fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h), squeeze=False)

    for ax_row in axes:
        for ax in ax_row:
            ax.axis("off")

    # Build heatmap for each cluster
    for k_idx in range(n_clusters):
        r, c = divmod(k_idx, cols)
        ax = axes[r][c]

        mask = labels == k_idx
        if not mask.any():
            continue

        patch_rows = positions[mask, 1] + patch_size // 2   # centre row
        patch_cols = positions[mask, 2] + patch_size // 2   # centre col

        heatmap, _, _ = np.histogram2d(
            patch_rows,
            patch_cols,
            bins=32,
            range=[[0, sdf_size], [0, sdf_size]],
        )

        ax.imshow(
            heatmap,
            cmap=hcmap,
            origin="upper",
            extent=[0, sdf_size, sdf_size, 0],
            interpolation="nearest",
        )
        ax.set_title(
            str(k_idx),
            fontsize=max(2, thumb_px // 12),
            pad=1,
        )
        ax.axis("off")

    fig.suptitle(
        f"Patch position heatmaps  –  {n_clusters} clusters  "
        f"(bright = frequent location)",
        fontsize=max(6, thumb_px // 8),
        y=1.001,
    )
    fig.tight_layout(pad=0.1)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Heatmap saved: {out_path}  ({n_clusters} clusters, {rows}×{cols} grid)")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualise SDF parts dictionary (gallery + position heatmaps).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--kmeans", required=True, metavar="PATH",
        help=".npz cluster dictionary produced by patch_kmeans.py.",
    )
    parser.add_argument(
        "--features", metavar="PATH",
        help=".npz feature file produced by patch_extractor.py (enables heatmaps).",
    )
    parser.add_argument(
        "--out", metavar="PATH",
        help=(
            "Output PNG path for the parts gallery "
            "(default: parts_gallery.png next to --kmeans)."
        ),
    )
    parser.add_argument(
        "--heatmap", metavar="PATH",
        help="Output PNG path for position heatmaps (requires --features).",
    )
    parser.add_argument(
        "--sdf-size", type=int, default=256, metavar="PX",
        help="Pixel side-length of original SDF images (default: 256).",
    )
    parser.add_argument(
        "--cols", type=int, default=8, metavar="N",
        help="Grid columns (default: 8).",
    )
    parser.add_argument(
        "--thumb", type=int, default=96, metavar="PX",
        help="Thumbnail pixel size (default: 96).",
    )
    parser.add_argument(
        "--cmap", default="RdBu_r", metavar="NAME",
        help="Matplotlib colormap for patch thumbnails (default: RdBu_r).",
    )
    parser.add_argument(
        "--hcmap", default="hot", metavar="NAME",
        help="Matplotlib colormap for heatmaps (default: hot).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    kmeans_path = Path(args.kmeans)
    if not kmeans_path.exists():
        sys.exit(f"ERROR: Cluster file not found: {kmeans_path}")

    kmeans_data = _load_kmeans(kmeans_path)

    # --- Gallery -----------------------------------------------------------
    gallery_out = (
        Path(args.out)
        if args.out
        else kmeans_path.parent / "parts_gallery.png"
    )
    visualise_gallery(
        kmeans_data,
        out_path=gallery_out,
        cols=args.cols,
        thumb_px=args.thumb,
        cmap=args.cmap,
    )

    # --- Heatmaps ----------------------------------------------------------
    if args.heatmap:
        if not args.features:
            sys.exit(
                "ERROR: --heatmap requires --features (position data is in the "
                "features .npz file)."
            )
        feat_path = Path(args.features)
        if not feat_path.exists():
            sys.exit(f"ERROR: Feature file not found: {feat_path}")

        features_data = _load_features(feat_path)

        heatmap_out = Path(args.heatmap)
        visualise_heatmaps(
            kmeans_data,
            features_data,
            out_path=heatmap_out,
            sdf_size=args.sdf_size,
            cols=args.cols,
            thumb_px=args.thumb,
            hcmap=args.hcmap,
        )


if __name__ == "__main__":
    main()
