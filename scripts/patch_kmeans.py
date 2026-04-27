"""
patch_kmeans.py
===============
Cluster SDF patch features (produced by patch_extractor.py) using PCA
dimensionality-reduction followed by k-means, and save the resulting
"parts dictionary" as a compressed NumPy archive.

Pipeline
--------
1. Load the feature matrix from a .npz file (see patch_extractor.py).
2. Normalise each patch vector to zero mean / unit variance (StandardScaler).
3. Reduce dimensionality with PCA.
4. Run k-means on the reduced vectors.
5. Save cluster labels, PCA-space centres, and representative raw patches
   (the patch closest to each cluster centroid) to an output .npz file.

The output archive contains:
  labels        – (N,) int32   cluster index for every input patch
  centers_pca   – (k, n_pca) float32  cluster centroids in PCA space
  rep_patches   – (k, patch_size, patch_size) float32  representative patches
  rep_indices   – (k,) int64  index into features of each representative patch
  n_clusters    – scalar  k
  n_pca         – scalar  actual PCA components used
  patch_size    – scalar  patch edge length

Usage
-----
    python scripts/patch_kmeans.py \\
        --features out/patches/patches.npz \\
        --out      out/patches/kmeans.npz

    # more clusters, fewer PCA components
    python scripts/patch_kmeans.py \\
        --features out/patches/patches.npz \\
        --out      out/patches/kmeans.npz \\
        --clusters 128 \\
        --pca 32 \\
        --seed 0

Arguments
---------
--features      Path to the .npz produced by patch_extractor.py.
--out           Output .npz path for the cluster dictionary.
--clusters      Number of k-means clusters / "parts" (default: 64).
--pca           Number of PCA components (default: 64; capped at min(N, D)).
--seed          Random seed (default: 42).
--max-iter      k-means maximum iterations (default: 300).
--n-init        Number of k-means random initialisations (default: 10).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Core clustering
# ---------------------------------------------------------------------------

def cluster_patches(
    features: np.ndarray,
    patch_size: int,
    *,
    n_clusters: int = 64,
    n_pca: int = 64,
    seed: int = 42,
    max_iter: int = 300,
    n_init: int = 10,
) -> dict:
    """Run PCA + k-means on *features* and return a result dictionary.

    Parameters
    ----------
    features:
        (N, D) float32 patch feature matrix.
    patch_size:
        Edge length of each square patch (used to reshape representative patches).

    Returns
    -------
    dict with keys:
        labels, centers_pca, rep_patches, rep_indices, n_clusters, n_pca,
        patch_size, explained_variance_ratio
    """
    N, D = features.shape

    # --- Normalise ---------------------------------------------------------
    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    # --- PCA ---------------------------------------------------------------
    actual_pca = min(n_pca, N, D)
    print(f"PCA: {D} → {actual_pca} components …", flush=True)
    pca = PCA(n_components=actual_pca, random_state=seed)
    X_pca = pca.fit_transform(X).astype(np.float32)
    var_ratio = pca.explained_variance_ratio_
    print(
        f"  Cumulative explained variance: "
        f"{100 * var_ratio.sum():.1f}%  "
        f"(first 10: {100 * var_ratio[:10].sum():.1f}%)"
    )

    # --- k-means -----------------------------------------------------------
    actual_k = min(n_clusters, N)
    print(f"k-means: k={actual_k}, n_init={n_init}, max_iter={max_iter} …", flush=True)

    # Use MiniBatchKMeans for large datasets (>50 000 samples)
    if N > 50_000:
        km = MiniBatchKMeans(
            n_clusters=actual_k,
            random_state=seed,
            max_iter=max_iter,
            n_init=n_init,
        )
    else:
        km = KMeans(
            n_clusters=actual_k,
            random_state=seed,
            max_iter=max_iter,
            n_init=n_init,
        )

    labels = km.fit_predict(X_pca).astype(np.int32)
    centers_pca = km.cluster_centers_.astype(np.float32)

    # --- Representative patches (closest to centroid in PCA space) ---------
    rep_indices = np.empty(actual_k, dtype=np.int64)
    for k_idx in range(actual_k):
        mask = labels == k_idx
        if not mask.any():
            rep_indices[k_idx] = 0
            continue
        cluster_vecs = X_pca[mask]
        cluster_orig_idx = np.where(mask)[0]
        dists = np.linalg.norm(cluster_vecs - centers_pca[k_idx], axis=1)
        rep_indices[k_idx] = cluster_orig_idx[int(np.argmin(dists))]

    rep_patches = features[rep_indices].reshape(actual_k, patch_size, patch_size)

    print(
        f"Clustering done.  k={actual_k}, "
        f"inertia={km.inertia_:.2f}"
    )

    return {
        "labels": labels,
        "centers_pca": centers_pca,
        "rep_patches": rep_patches.astype(np.float32),
        "rep_indices": rep_indices,
        "n_clusters": np.int32(actual_k),
        "n_pca": np.int32(actual_pca),
        "patch_size": np.int32(patch_size),
        "explained_variance_ratio": var_ratio.astype(np.float32),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PCA + k-means clustering of SDF patch features.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--features", required=True, metavar="PATH",
        help=".npz feature file produced by patch_extractor.py.",
    )
    parser.add_argument(
        "--out", required=True, metavar="PATH",
        help="Output .npz path for the cluster dictionary.",
    )
    parser.add_argument(
        "--clusters", type=int, default=64, metavar="K",
        help="Number of k-means clusters (default: 64).",
    )
    parser.add_argument(
        "--pca", type=int, default=64, metavar="N",
        help="Number of PCA components (default: 64).",
    )
    parser.add_argument(
        "--seed", type=int, default=42, metavar="N",
        help="Random seed (default: 42).",
    )
    parser.add_argument(
        "--max-iter", type=int, default=300, metavar="N",
        help="k-means maximum iterations (default: 300).",
    )
    parser.add_argument(
        "--n-init", type=int, default=10, metavar="N",
        help="k-means random initialisations (default: 10).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    feat_path = Path(args.features)
    if not feat_path.exists():
        sys.exit(f"ERROR: Feature file not found: {feat_path}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Load ---------------------------------------------------------------
    print(f"Loading features from {feat_path} …")
    data = np.load(feat_path, allow_pickle=True)
    features = data["features"].astype(np.float32)
    patch_size = int(data["patch_size"])
    positions = data["positions"]           # kept for downstream use
    sources = data["sources"]               # kept for downstream use
    print(f"  features shape: {features.shape}  patch_size: {patch_size}")

    if features.shape[0] < 2:
        sys.exit("ERROR: Need at least 2 patches for clustering.")

    # --- Cluster ------------------------------------------------------------
    result = cluster_patches(
        features,
        patch_size,
        n_clusters=args.clusters,
        n_pca=args.pca,
        seed=args.seed,
        max_iter=args.max_iter,
        n_init=args.n_init,
    )

    # --- Save ---------------------------------------------------------------
    np.savez_compressed(
        out_path,
        labels=result["labels"],
        centers_pca=result["centers_pca"],
        rep_patches=result["rep_patches"],
        rep_indices=result["rep_indices"],
        n_clusters=result["n_clusters"],
        n_pca=result["n_pca"],
        patch_size=result["patch_size"],
        explained_variance_ratio=result["explained_variance_ratio"],
        # pass through source metadata so viz_parts.py can load one file
        positions=positions,
        sources=sources,
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
