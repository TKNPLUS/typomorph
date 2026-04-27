"""
demo_parts.py
=============
Standalone demonstration script for exploring and applying the parts
dictionary produced by the patch_kmeans.py pipeline.

Sub-commands
------------
show-patch
    Display (or save) the representative SDF patch for a single cluster.

morph
    Linearly interpolate between two cluster representative patches in PCA
    space and render the interpolated sequence as a grid image.

reconstruct
    Reconstruct each SDF in a directory using its nearest-neighbour
    cluster patches, then visualise original vs. reconstructed vs. residual
    and report MSE / PSNR metrics per character.

gallery-stats
    Compute per-cluster statistics (count, mean patch-centre row/col,
    row/col standard deviation) and write them to a CSV file.

decompose
    For each character in the dataset, compute its cluster-assignment
    histogram (how many of its patches fall in each cluster) and write the
    result as a CSV bag-of-parts representation.

Usage examples
--------------
    # Show / save cluster 5's representative patch
    python scripts/demo_parts.py show-patch \\
        --kmeans out/patches/kmeans.npz \\
        --cluster 5 \\
        --out out/patches/patch_5.png

    # 8-step morph from cluster 3 → cluster 27
    python scripts/demo_parts.py morph \\
        --kmeans out/patches/kmeans.npz \\
        --from 3 --to 27 --steps 8 \\
        --out out/patches/morph_3_27.png

    # Reconstruct one SDF and report metrics
    python scripts/demo_parts.py reconstruct \\
        --kmeans   out/patches/kmeans.npz \\
        --features out/patches/patches.npz \\
        --sdf      out/sdf \\
        --out      out/patches/reconstruction

    # Export per-cluster statistics to CSV
    python scripts/demo_parts.py gallery-stats \\
        --kmeans   out/patches/kmeans.npz \\
        --features out/patches/patches.npz \\
        --out      out/patches/cluster_stats.csv

    # Export per-character bag-of-parts vectors to CSV
    python scripts/demo_parts.py decompose \\
        --kmeans   out/patches/kmeans.npz \\
        --features out/patches/patches.npz \\
        --out      out/patches/char_vectors.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_npz(path: Path) -> dict:
    data = np.load(path, allow_pickle=True)
    return {k: data[k] for k in data.files}


def _pca_inverse(centers_pca: np.ndarray, kmeans_data: dict) -> np.ndarray:
    """Inverse-transform PCA-space vectors back to patch pixel space.

    Parameters
    ----------
    centers_pca:
        Shape ``(m, pca_dim)``.
    kmeans_data:
        Dictionary loaded from ``kmeans.npz``.

    Returns
    -------
    patches:
        Shape ``(m, patch_size, patch_size)``, float32.
    """
    components = kmeans_data["pca_components"]   # (pca_dim, flat_patch)
    mean = kmeans_data["pca_mean"]               # (flat_patch,)
    patch_size = int(kmeans_data["patch_size"])

    flat = centers_pca @ components + mean       # (m, flat_patch)
    return flat.reshape(-1, patch_size, patch_size).astype(np.float32)


# ---------------------------------------------------------------------------
# Sub-command: show-patch
# ---------------------------------------------------------------------------

def cmd_show_patch(args: argparse.Namespace) -> None:
    """Display or save a single cluster's representative patch."""
    kmeans_data = _load_npz(Path(args.kmeans))
    n_clusters = int(kmeans_data["n_clusters"])

    if args.cluster < 0 or args.cluster >= n_clusters:
        sys.exit(
            f"ERROR: --cluster must be in [0, {n_clusters - 1}], "
            f"got {args.cluster}."
        )

    patch = kmeans_data["rep_patches"][args.cluster]
    labels = kmeans_data["labels"]
    count = int(np.sum(labels == args.cluster))
    vmax = float(np.abs(patch).max()) or 1.0

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(patch, cmap=args.cmap, vmin=-vmax, vmax=vmax,
              origin="upper", interpolation="nearest")
    ax.contour(patch, levels=[0.0], colors="white", linewidths=0.8)
    ax.set_title(
        f"Cluster {args.cluster}  ({count} patches)\n"
        f"Blue=inside / Red=outside / White=outline",
        fontsize=9,
    )
    ax.axis("off")
    fig.tight_layout()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {out_path}")
    else:
        plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# Sub-command: morph
# ---------------------------------------------------------------------------

def cmd_morph(args: argparse.Namespace) -> None:
    """Interpolate between two cluster centroids in PCA space."""
    kmeans_data = _load_npz(Path(args.kmeans))
    n_clusters = int(kmeans_data["n_clusters"])

    for label, val in [("--from", args.from_cluster), ("--to", args.to_cluster)]:
        if val < 0 or val >= n_clusters:
            sys.exit(
                f"ERROR: {label} must be in [0, {n_clusters - 1}], got {val}."
            )

    centers = kmeans_data["centers"]             # (k, pca_dim)
    c_from = centers[args.from_cluster]
    c_to = centers[args.to_cluster]

    steps = max(2, args.steps)
    ts = np.linspace(0.0, 1.0, steps)
    interpolated_pca = np.stack(
        [(1 - t) * c_from + t * c_to for t in ts]
    )                                            # (steps, pca_dim)

    patches = _pca_inverse(interpolated_pca, kmeans_data)   # (steps, H, W)

    cols = steps
    rows = 1
    dpi = 100
    thumb_px = args.thumb
    cell_in = thumb_px / dpi
    fig, axes = plt.subplots(rows, cols,
                             figsize=(cols * cell_in, rows * cell_in),
                             squeeze=False)

    for i, ax in enumerate(axes[0]):
        patch = patches[i]
        vmax = float(np.abs(patch).max()) or 1.0
        ax.imshow(patch, cmap=args.cmap, vmin=-vmax, vmax=vmax,
                  origin="upper", interpolation="nearest")
        ax.contour(patch, levels=[0.0], colors="white", linewidths=0.3)
        ax.set_title(f"t={ts[i]:.2f}", fontsize=max(4, thumb_px // 16), pad=1)
        ax.axis("off")

    fig.suptitle(
        f"Morph: cluster {args.from_cluster} → {args.to_cluster}  "
        f"({steps} steps)",
        fontsize=max(6, thumb_px // 10),
        y=1.01,
    )
    fig.tight_layout(pad=0.2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Morph saved: {out_path}  ({steps} steps, "
          f"cluster {args.from_cluster} → {args.to_cluster})")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Sub-command: reconstruct
# ---------------------------------------------------------------------------

def cmd_reconstruct(args: argparse.Namespace) -> None:
    """Reconstruct SDFs from the parts dictionary and report metrics."""
    kmeans_data = _load_npz(Path(args.kmeans))
    features_data = _load_npz(Path(args.features))

    sdf_dir = Path(args.sdf)
    if not sdf_dir.is_dir():
        sys.exit(f"ERROR: SDF directory not found: {sdf_dir}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rep_patches = kmeans_data["rep_patches"]     # (k, H, W)
    labels = features_data["labels"] if "labels" in features_data else kmeans_data["labels"]
    positions = features_data["positions"]       # (N, 3): [file_idx, row, col]
    file_ids = features_data.get("file_ids", features_data.get("sources"))
    patch_size = int(kmeans_data["patch_size"])
    n_clusters = int(kmeans_data["n_clusters"])

    sdf_size = args.sdf_size
    metrics: list[dict] = []

    # Limit to --max-chars characters for speed
    all_file_ids = list(file_ids)
    if args.max_chars > 0:
        all_file_ids = all_file_ids[: args.max_chars]

    for fid in all_file_ids:
        npy_path = sdf_dir / f"{fid}.npy"
        if not npy_path.exists():
            continue

        original = np.load(npy_path).astype(np.float32)
        if original.shape != (sdf_size, sdf_size):
            continue

        # Reconstruct: paste representative patch at each stored position
        reconstructed = np.zeros((sdf_size, sdf_size), dtype=np.float32)
        weight = np.zeros((sdf_size, sdf_size), dtype=np.float32)

        fidx = int(np.where(file_ids == fid)[0][0])
        mask = positions[:, 0] == fidx

        for i in np.where(mask)[0]:
            r0 = int(positions[i, 1])
            c0 = int(positions[i, 2])
            r1 = min(r0 + patch_size, sdf_size)
            c1 = min(c0 + patch_size, sdf_size)
            ph = r1 - r0
            pw = c1 - c0
            lbl = int(labels[i])
            reconstructed[r0:r1, c0:c1] += rep_patches[lbl, :ph, :pw]
            weight[r0:r1, c0:c1] += 1.0

        covered = weight > 0
        reconstructed[covered] /= weight[covered]

        # Metrics on covered region
        if covered.any():
            diff = original[covered] - reconstructed[covered]
            mse = float(np.mean(diff ** 2))
            max_val = float(np.abs(original).max()) or 1.0
            psnr = (
                10.0 * math.log10(max_val ** 2 / mse)
                if mse > 0
                else float("inf")
            )
            coverage = float(covered.mean())
        else:
            mse, psnr, coverage = float("nan"), float("nan"), 0.0

        metrics.append({
            "file_id": fid,
            "mse": mse,
            "psnr_db": psnr,
            "coverage": coverage,
        })
        print(
            f"  {fid:>12s}  MSE={mse:7.4f}  PSNR={psnr:6.2f} dB  "
            f"coverage={coverage:.1%}"
        )

        # Save comparison figure if requested
        if args.save_figures:
            residual = original - reconstructed
            fig, axes = plt.subplots(1, 3, figsize=(9, 3))
            for ax, img, title in zip(
                axes,
                [original, reconstructed, residual],
                ["Original SDF", "Reconstructed", "Residual"],
            ):
                vmax = float(np.abs(img).max()) or 1.0
                ax.imshow(img, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                          origin="upper")
                ax.contour(img, levels=[0.0], colors="white", linewidths=0.5)
                ax.set_title(title, fontsize=9)
                ax.axis("off")
            fig.suptitle(
                f"{fid}  |  MSE={mse:.4f}  PSNR={psnr:.2f} dB",
                fontsize=9,
            )
            fig.tight_layout()
            fig.savefig(out_dir / f"{fid}_reconstruct.png",
                        dpi=100, bbox_inches="tight")
            plt.close(fig)

    # Write metrics CSV
    csv_path = out_dir / "reconstruction_metrics.csv"
    if metrics:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["file_id", "mse", "psnr_db", "coverage"]
            )
            writer.writeheader()
            writer.writerows(metrics)

        mse_vals = [m["mse"] for m in metrics if not math.isnan(m["mse"])]
        psnr_vals = [m["psnr_db"] for m in metrics
                     if not math.isinf(m["psnr_db"]) and not math.isnan(m["psnr_db"])]
        print(
            f"\nSummary ({len(metrics)} characters):\n"
            f"  Mean MSE  = {np.mean(mse_vals):.4f}\n"
            f"  Mean PSNR = {np.mean(psnr_vals):.2f} dB\n"
            f"  Metrics CSV: {csv_path}"
        )
    else:
        print("No characters processed.")


# ---------------------------------------------------------------------------
# Sub-command: gallery-stats
# ---------------------------------------------------------------------------

def cmd_gallery_stats(args: argparse.Namespace) -> None:
    """Write per-cluster statistics (count, centroid, spread) to CSV."""
    kmeans_data = _load_npz(Path(args.kmeans))
    n_clusters = int(kmeans_data["n_clusters"])
    labels = kmeans_data["labels"]

    rows: list[dict] = []

    if args.features:
        features_data = _load_npz(Path(args.features))
        positions = features_data["positions"]   # (N, 3): [file_idx, row, col]
        patch_size = int(kmeans_data["patch_size"])

        for k in range(n_clusters):
            mask = labels == k
            count = int(mask.sum())
            if count == 0:
                rows.append({
                    "cluster": k, "count": 0,
                    "mean_row": "", "mean_col": "",
                    "std_row": "", "std_col": "",
                })
                continue
            centre_rows = positions[mask, 1] + patch_size // 2
            centre_cols = positions[mask, 2] + patch_size // 2
            rows.append({
                "cluster": k,
                "count": count,
                "mean_row": float(np.mean(centre_rows)),
                "mean_col": float(np.mean(centre_cols)),
                "std_row": float(np.std(centre_rows)),
                "std_col": float(np.std(centre_cols)),
            })
    else:
        counts = np.bincount(labels, minlength=n_clusters)
        for k in range(n_clusters):
            rows.append({
                "cluster": k,
                "count": int(counts[k]),
                "mean_row": "",
                "mean_col": "",
                "std_row": "",
                "std_col": "",
            })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["cluster", "count",
                        "mean_row", "mean_col", "std_row", "std_col"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Cluster stats saved: {out_path}  ({n_clusters} clusters)")


# ---------------------------------------------------------------------------
# Sub-command: decompose
# ---------------------------------------------------------------------------

def cmd_decompose(args: argparse.Namespace) -> None:
    """Write per-character cluster-assignment histograms (bag-of-parts) to CSV."""
    kmeans_data = _load_npz(Path(args.kmeans))
    features_data = _load_npz(Path(args.features))

    n_clusters = int(kmeans_data["n_clusters"])
    labels = kmeans_data["labels"]               # (N,)
    positions = features_data["positions"]       # (N, 3): [file_idx, row, col]
    file_ids = features_data.get("file_ids", features_data.get("sources"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["file_id"] + [f"cluster_{k}" for k in range(n_clusters)]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for fidx, fid in enumerate(file_ids):
            mask = positions[:, 0] == fidx
            file_labels = labels[mask]
            hist = np.bincount(file_labels, minlength=n_clusters)
            row: dict = {"file_id": str(fid)}
            row.update({f"cluster_{k}": int(hist[k]) for k in range(n_clusters)})
            writer.writerow(row)

    print(
        f"Decomposition saved: {out_path}  "
        f"({len(file_ids)} characters, {n_clusters} clusters)"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demo_parts",
        description="Explore and apply the typomorph parts dictionary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- show-patch ----
    p_show = sub.add_parser(
        "show-patch",
        help="Display the representative patch for one cluster.",
    )
    p_show.add_argument("--kmeans", required=True, metavar="PATH",
                        help=".npz cluster dictionary (patch_kmeans.py output).")
    p_show.add_argument("--cluster", type=int, required=True, metavar="K",
                        help="Cluster index to display.")
    p_show.add_argument("--cmap", default="RdBu_r", metavar="NAME",
                        help="Matplotlib colormap (default: RdBu_r).")
    p_show.add_argument("--out", metavar="PATH",
                        help="Save PNG to this path (omit for interactive display).")

    # ---- morph ----
    p_morph = sub.add_parser(
        "morph",
        help="Linearly interpolate between two cluster centroids.",
    )
    p_morph.add_argument("--kmeans", required=True, metavar="PATH",
                         help=".npz cluster dictionary.")
    p_morph.add_argument("--from", dest="from_cluster", type=int,
                         required=True, metavar="K",
                         help="Source cluster index.")
    p_morph.add_argument("--to", dest="to_cluster", type=int,
                         required=True, metavar="K",
                         help="Target cluster index.")
    p_morph.add_argument("--steps", type=int, default=8, metavar="N",
                         help="Number of interpolation steps (default: 8).")
    p_morph.add_argument("--thumb", type=int, default=96, metavar="PX",
                         help="Thumbnail pixel size (default: 96).")
    p_morph.add_argument("--cmap", default="RdBu_r", metavar="NAME",
                         help="Matplotlib colormap (default: RdBu_r).")
    p_morph.add_argument("--out", required=True, metavar="PATH",
                         help="Output PNG path.")

    # ---- reconstruct ----
    p_rec = sub.add_parser(
        "reconstruct",
        help="Reconstruct SDFs from parts dictionary and report metrics.",
    )
    p_rec.add_argument("--kmeans", required=True, metavar="PATH",
                       help=".npz cluster dictionary.")
    p_rec.add_argument("--features", required=True, metavar="PATH",
                       help=".npz feature file (patch_extractor.py output).")
    p_rec.add_argument("--sdf", required=True, metavar="DIR",
                       help="Directory containing .npy SDF files.")
    p_rec.add_argument("--out", required=True, metavar="DIR",
                       help="Output directory for metrics CSV and figures.")
    p_rec.add_argument("--sdf-size", type=int, default=256, metavar="PX",
                       help="SDF image side length in pixels (default: 256).")
    p_rec.add_argument("--max-chars", type=int, default=50, metavar="N",
                       help="Maximum number of characters to process (default: 50; "
                            "set to 0 for all).")
    p_rec.add_argument("--save-figures", action="store_true",
                       help="Save original/reconstructed/residual PNG per character.")

    # ---- gallery-stats ----
    p_gs = sub.add_parser(
        "gallery-stats",
        help="Export per-cluster statistics to CSV.",
    )
    p_gs.add_argument("--kmeans", required=True, metavar="PATH",
                      help=".npz cluster dictionary.")
    p_gs.add_argument("--features", metavar="PATH",
                      help=".npz feature file (enables centroid/spread columns).")
    p_gs.add_argument("--out", required=True, metavar="PATH",
                      help="Output CSV path.")

    # ---- decompose ----
    p_dec = sub.add_parser(
        "decompose",
        help="Export per-character bag-of-parts cluster histograms to CSV.",
    )
    p_dec.add_argument("--kmeans", required=True, metavar="PATH",
                       help=".npz cluster dictionary.")
    p_dec.add_argument("--features", required=True, metavar="PATH",
                       help=".npz feature file.")
    p_dec.add_argument("--out", required=True, metavar="PATH",
                       help="Output CSV path.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "show-patch": cmd_show_patch,
        "morph": cmd_morph,
        "reconstruct": cmd_reconstruct,
        "gallery-stats": cmd_gallery_stats,
        "decompose": cmd_decompose,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
