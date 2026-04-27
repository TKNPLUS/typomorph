"""
app.py
======
Streamlit GUI for the typomorph pipeline.

Covers the full data-generation and visualisation pipeline:
  ① PNG Rendering    – render characters from a font (render_png.py)
  ② SDF Generation   – compute Signed Distance Fields (make_sdf.py)
  ③ Patch Extraction – extract local patches from SDFs (patch_extractor.py)
  ④ Clustering       – PCA + k-means parts dictionary (patch_kmeans.py)
  ⑤ Visualisation    – gallery and heatmap output (viz_parts.py / viz_sdf.py)

All heavy computation reuses the same functions as the CLI scripts.

Launch
------
    streamlit run app.py

Docker
------
    docker run --rm -p 8501:8501 -v "$(pwd)":/work typomorph \\
        streamlit run app.py --server.address 0.0.0.0
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import streamlit as st

# ---------------------------------------------------------------------------
# Make scripts/ importable without installing a package
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from render_png import render_char, _fc_match  # noqa: E402
from make_sdf import png_to_sdf  # noqa: E402
from patch_extractor import extract_all  # noqa: E402
from patch_kmeans import cluster_patches  # noqa: E402
from viz_parts import (  # noqa: E402
    visualise_gallery as _parts_gallery,
    visualise_heatmaps as _parts_heatmaps,
    _load_kmeans,
    _load_features,
)
from viz_sdf import visualise_gallery as _sdf_gallery  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="typomorph",
    page_icon="🈳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🈳 typomorph — 漢字形状解析パイプライン")
st.caption(
    "① PNG レンダリング → ② SDF 生成 → ③ パッチ抽出 → ④ クラスタリング → ⑤ 可視化"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _capture_logs():
    """Redirect stdout/stderr to a StringIO buffer."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        yield buf


def _read_chars(list_path: str | Path) -> list[str]:
    """Read a one-char-per-line text file and return a list of characters."""
    p = Path(list_path)
    if not p.exists():
        raise FileNotFoundError(f"文字リストが見つかりません: {p}")
    chars: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            chars.append(stripped[0])
    if not chars:
        raise ValueError(f"文字が1つも見つかりません: {p}")
    return chars


def _show_image_grid(
    image_paths: list[Path],
    max_show: int = 24,
    n_cols: int = 8,
) -> None:
    """Render a thumbnail grid for a list of image paths."""
    paths = image_paths[:max_show]
    if not paths:
        return
    cols = st.columns(min(n_cols, len(paths)))
    for i, path in enumerate(paths):
        with cols[i % n_cols]:
            st.image(str(path), caption=path.stem, use_container_width=True)


def _pipeline_status(root: str) -> None:
    """Show a status badge for each pipeline stage based on output files."""
    r = Path(root)
    stages = [
        ("① PNG", r / "png"),
        ("② SDF", r / "sdf"),
        ("③ Patches", r / "patches" / "patches.npz"),
        ("④ Kmeans", r / "patches" / "kmeans.npz"),
        ("⑤ Gallery", r / "patches" / "parts_gallery.png"),
    ]
    st.markdown("**パイプライン状態**")
    for label, path in stages:
        exists = path.exists() if path.suffix else any(path.glob("*")) if path.is_dir() else False
        icon = "✅" if exists else "⬜"
        st.markdown(f"{icon} {label}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 共通設定")
    root_dir = st.text_input(
        "出力ルートディレクトリ",
        value="out",
        help="各ステージの出力先の親ディレクトリ。",
    )
    st.markdown("---")
    _pipeline_status(root_dir)
    st.markdown("---")
    st.markdown(
        "**使い方**\n"
        "1. 各タブのパラメータを確認・設定\n"
        "2. ▶ ボタンで処理実行\n"
        "3. 結果を確認してから次のタブへ"
    )
    st.markdown("---")
    st.markdown(
        "**CLI との対応**\n"
        "- `render_png.py` → ① タブ\n"
        "- `make_sdf.py`   → ② タブ\n"
        "- `patch_extractor.py` → ③ タブ\n"
        "- `patch_kmeans.py`    → ④ タブ\n"
        "- `viz_parts.py`       → ⑤ タブ\n"
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "① PNG レンダリング",
        "② SDF 生成",
        "③ パッチ抽出",
        "④ クラスタリング",
        "⑤ 可視化",
    ]
)


# ===========================================================================
# Tab 1 – PNG Rendering
# ===========================================================================
with tab1:
    st.header("① PNG レンダリング")
    st.markdown(
        "文字リストの各文字をフォントからレンダリングして正規化 PNG を生成します。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        t1_list = st.text_input(
            "文字リスト (.txt)",
            "lists/joyo.txt",
            key="t1_list",
            help="1行1文字の UTF-8 テキストファイル。",
        )
        t1_font = st.text_input(
            "フォントファミリー名",
            "Noto Sans CJK JP",
            key="t1_font",
            help="fc-match で解決するフォントファミリー名。",
        )
        t1_out = st.text_input(
            "出力ディレクトリ",
            f"{root_dir}/png",
            key="t1_out",
        )
    with col_b:
        t1_size = st.number_input(
            "キャンバスサイズ (px)", 64, 1024, 256, step=32, key="t1_size"
        )
        t1_margin = st.slider(
            "マージン比率", 0.0, 0.3, 0.10, 0.01, key="t1_margin"
        )
        t1_skip = st.checkbox("既存ファイルをスキップ", value=True, key="t1_skip")

    if st.button("▶ PNG レンダリング実行", key="run_t1", type="primary"):
        # Validate char list
        try:
            chars_t1 = _read_chars(t1_list)
        except (FileNotFoundError, ValueError) as exc:
            st.error(f"❌ {exc}")
            st.stop()

        # Resolve font
        try:
            font_path = _fc_match(t1_font)
        except SystemExit as exc:
            st.error(f"❌ フォントエラー: {exc}")
            st.stop()

        from PIL import ImageFont  # noqa: PLC0415

        try:
            pil_font = ImageFont.truetype(str(font_path), size=int(t1_size) * 2)
        except Exception as exc:
            st.error(f"❌ フォント読み込み失敗: {exc}")
            st.stop()

        out_dir_t1 = Path(t1_out)
        out_dir_t1.mkdir(parents=True, exist_ok=True)

        n = len(chars_t1)
        progress_bar = st.progress(0, text="レンダリング準備中…")
        rendered = skipped = 0

        for i, char in enumerate(chars_t1):
            cp = ord(char)
            out_path = out_dir_t1 / f"U+{cp:04X}.png"
            if t1_skip and out_path.exists():
                skipped += 1
            else:
                img = render_char(char, pil_font, int(t1_size), float(t1_margin))
                img.save(out_path)
                rendered += 1
            progress_bar.progress(
                (i + 1) / n,
                text=f"レンダリング中… {i + 1}/{n}",
            )

        progress_bar.empty()
        st.success(
            f"✅ 完了: rendered={rendered}, skipped={skipped}, total={n}"
        )

        png_files = sorted(out_dir_t1.glob("*.png"))
        if png_files:
            st.subheader(f"サムネイルプレビュー（先頭 24 件 / 全 {len(png_files)} 件）")
            _show_image_grid(png_files, max_show=24, n_cols=8)


# ===========================================================================
# Tab 2 – SDF Generation
# ===========================================================================
with tab2:
    st.header("② SDF 生成")
    st.markdown(
        "PNG 画像から Signed Distance Field (.npy) を生成します。  \n"
        "生成後、SDF ギャラリー PNG も自動で保存・表示します。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        t2_png = st.text_input(
            "PNG ディレクトリ", f"{root_dir}/png", key="t2_png"
        )
        t2_out = st.text_input(
            "出力ディレクトリ", f"{root_dir}/sdf", key="t2_out"
        )
        t2_list = st.text_input(
            "文字リスト (.txt)（省略可）",
            "lists/joyo.txt",
            key="t2_list",
            help="省略するとPNGディレクトリ内の全ファイルを処理します。",
        )
    with col_b:
        t2_clip = st.number_input(
            "クリップ距離 (px)", 1.0, 256.0, 32.0, step=1.0, key="t2_clip"
        )
        t2_thresh = st.slider(
            "2値化しきい値 (0–255)", 0, 255, 128, key="t2_thresh"
        )
        t2_skip = st.checkbox("既存ファイルをスキップ", value=True, key="t2_skip")

    if st.button("▶ SDF 生成実行", key="run_t2", type="primary"):
        png_dir_t2 = Path(t2_png)
        if not png_dir_t2.is_dir():
            st.error(f"❌ PNG ディレクトリが見つかりません: {png_dir_t2}")
            st.stop()

        # Optionally restrict to char list
        chars_t2: list[str] | None = None
        if t2_list.strip():
            try:
                chars_t2 = _read_chars(t2_list)
            except (FileNotFoundError, ValueError) as exc:
                st.error(f"❌ {exc}")
                st.stop()

        if chars_t2 is not None:
            png_files_t2 = [
                png_dir_t2 / f"U+{ord(ch):04X}.png" for ch in chars_t2
            ]
        else:
            png_files_t2 = sorted(png_dir_t2.glob("*.png"))

        if not png_files_t2:
            st.error("❌ PNG ファイルが見つかりません。")
            st.stop()

        out_dir_t2 = Path(t2_out)
        out_dir_t2.mkdir(parents=True, exist_ok=True)

        n = len(png_files_t2)
        progress_bar = st.progress(0, text="SDF 生成準備中…")
        done = skipped = missing = 0

        for i, png_path in enumerate(png_files_t2):
            out_path = out_dir_t2 / f"{png_path.stem}.npy"
            if t2_skip and out_path.exists():
                skipped += 1
            elif not png_path.exists():
                missing += 1
            else:
                sdf = png_to_sdf(
                    png_path,
                    clip=float(t2_clip),
                    threshold=int(t2_thresh),
                )
                np.save(out_path, sdf)
                done += 1
            progress_bar.progress(
                (i + 1) / n,
                text=f"SDF 生成中… {i + 1}/{n}",
            )

        progress_bar.empty()
        st.success(
            f"✅ 完了: generated={done}, skipped={skipped}, "
            f"missing_png={missing}, total={n}"
        )

        # Auto-generate SDF gallery for preview
        npy_files_t2 = sorted(out_dir_t2.glob("*.npy"))
        if npy_files_t2:
            gallery_path_t2 = out_dir_t2 / "sdf_gallery.png"
            with st.spinner("SDF ギャラリー生成中…"):
                with _capture_logs() as _log:
                    try:
                        _sdf_gallery(
                            out_dir_t2,
                            char_list=chars_t2,
                            out_path=gallery_path_t2,
                            cols=16,
                            thumb_px=48,
                        )
                    except SystemExit:
                        pass

            if gallery_path_t2.exists():
                st.subheader("SDF ギャラリー")
                st.image(str(gallery_path_t2), use_container_width=True)


# ===========================================================================
# Tab 3 – Patch Extraction
# ===========================================================================
with tab3:
    st.header("③ パッチ抽出")
    st.markdown(
        "SDF ファイルから局所パッチ（SDF=0 輪郭付近）を抽出して "
        "特徴量行列 (.npz) として保存します。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        t3_sdf = st.text_input(
            "SDF ディレクトリ", f"{root_dir}/sdf", key="t3_sdf"
        )
        t3_out = st.text_input(
            "出力 .npz ファイル",
            f"{root_dir}/patches/patches.npz",
            key="t3_out",
        )
        t3_list = st.text_input(
            "文字リスト (.txt)（省略可）",
            "",
            key="t3_list",
            help="省略するとSDFディレクトリ内の全ファイルを処理します。",
        )
    with col_b:
        t3_patch = st.selectbox(
            "パッチサイズ (px)", [32, 64, 128], index=1, key="t3_patch"
        )
        t3_border = st.number_input(
            "境界パッチ数/文字", 1, 200, 20, key="t3_border"
        )
        t3_random = st.number_input(
            "ランダムパッチ数/文字", 0, 100, 0, key="t3_random"
        )
        t3_margin = st.number_input(
            "境界マージン (px)", 1.0, 64.0, 8.0, step=1.0, key="t3_margin"
        )
        t3_seed = st.number_input("乱数シード", 0, 9999, 42, key="t3_seed")

    if st.button("▶ パッチ抽出実行", key="run_t3", type="primary"):
        sdf_dir_t3 = Path(t3_sdf)
        if not sdf_dir_t3.is_dir():
            st.error(f"❌ SDF ディレクトリが見つかりません: {sdf_dir_t3}")
            st.stop()

        char_list_t3: list[str] | None = None
        if t3_list.strip():
            try:
                char_list_t3 = _read_chars(t3_list)
            except (FileNotFoundError, ValueError) as exc:
                st.error(f"❌ {exc}")
                st.stop()

        out_path_t3 = Path(t3_out)
        out_path_t3.parent.mkdir(parents=True, exist_ok=True)

        with st.spinner("パッチ抽出中…（文字数が多いと数分かかります）"):
            with _capture_logs() as log_buf_t3:
                try:
                    features_t3, positions_t3, sources_t3 = extract_all(
                        sdf_dir_t3,
                        char_list=char_list_t3,
                        patch_size=int(t3_patch),
                        n_border=int(t3_border),
                        n_random=int(t3_random),
                        border_margin=float(t3_margin),
                        seed=int(t3_seed),
                    )
                except SystemExit as exc:
                    st.error(f"❌ {exc}")
                    st.stop()
                except Exception as exc:
                    st.error(f"❌ エラー: {exc}")
                    st.stop()

        np.savez_compressed(
            out_path_t3,
            features=features_t3,
            positions=positions_t3,
            sources=np.array(sources_t3, dtype=object),
            patch_size=np.int32(int(t3_patch)),
        )

        st.success(
            f"✅ 完了: {features_t3.shape[0]:,} パッチ抽出  "
            f"（{len(sources_t3)} 文字, パッチサイズ={t3_patch}px）"
        )
        st.info(f"保存先: `{out_path_t3}`")

        log_t3 = log_buf_t3.getvalue()
        if log_t3:
            with st.expander("ログ"):
                st.code(log_t3)


# ===========================================================================
# Tab 4 – Clustering
# ===========================================================================
with tab4:
    st.header("④ クラスタリング")
    st.markdown(
        "PCA で次元削減後、k-means クラスタリングして  \n"
        "「部品辞書」(.npz) を生成します。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        t4_feat = st.text_input(
            "特徴量 .npz ファイル",
            f"{root_dir}/patches/patches.npz",
            key="t4_feat",
        )
        t4_out = st.text_input(
            "出力 .npz ファイル",
            f"{root_dir}/patches/kmeans.npz",
            key="t4_out",
        )
    with col_b:
        t4_k = st.selectbox(
            "クラスタ数 k", [16, 32, 64, 128, 256], index=2, key="t4_k"
        )
        t4_pca = st.selectbox(
            "PCA 次元数", [16, 32, 64, 128], index=2, key="t4_pca"
        )
        t4_seed = st.number_input("乱数シード", 0, 9999, 42, key="t4_seed")
        t4_maxiter = st.number_input(
            "k-means 最大反復回数", 10, 1000, 300, key="t4_maxiter"
        )
        t4_ninit = st.number_input(
            "k-means 初期化回数", 1, 50, 10, key="t4_ninit"
        )

    if st.button("▶ クラスタリング実行", key="run_t4", type="primary"):
        feat_path_t4 = Path(t4_feat)
        if not feat_path_t4.exists():
            st.error(f"❌ 特徴量ファイルが見つかりません: {feat_path_t4}")
            st.stop()

        with st.spinner("クラスタリング中…（数分かかる場合があります）"):
            with _capture_logs() as log_buf_t4:
                try:
                    data_t4 = np.load(feat_path_t4, allow_pickle=True)
                    features_t4 = data_t4["features"].astype(np.float32)
                    patch_size_t4 = int(data_t4["patch_size"])
                    positions_t4 = data_t4["positions"]
                    sources_t4 = data_t4["sources"]

                    result_t4 = cluster_patches(
                        features_t4,
                        patch_size_t4,
                        n_clusters=int(t4_k),
                        n_pca=int(t4_pca),
                        seed=int(t4_seed),
                        max_iter=int(t4_maxiter),
                        n_init=int(t4_ninit),
                    )
                except SystemExit as exc:
                    st.error(f"❌ {exc}")
                    st.stop()
                except Exception as exc:
                    st.error(f"❌ エラー: {exc}")
                    st.stop()

        out_path_t4 = Path(t4_out)
        out_path_t4.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            out_path_t4,
            labels=result_t4["labels"],
            centers_pca=result_t4["centers_pca"],
            rep_patches=result_t4["rep_patches"],
            rep_indices=result_t4["rep_indices"],
            n_clusters=result_t4["n_clusters"],
            n_pca=result_t4["n_pca"],
            patch_size=result_t4["patch_size"],
            explained_variance_ratio=result_t4["explained_variance_ratio"],
            positions=positions_t4,
            sources=sources_t4,
        )

        st.success(
            f"✅ 完了: k={result_t4['n_clusters']}, "
            f"PCA={result_t4['n_pca']}, "
            f"patches={features_t4.shape[0]:,}"
        )
        st.info(f"保存先: `{out_path_t4}`")

        log_t4 = log_buf_t4.getvalue()
        if log_t4:
            with st.expander("ログ"):
                st.code(log_t4)


# ===========================================================================
# Tab 5 – Visualisation
# ===========================================================================
with tab5:
    st.header("⑤ 可視化")
    st.markdown(
        "クラスタ辞書のギャラリー（代表パッチ一覧）と  \n"
        "位置ヒートマップ（パッチ出現位置）を生成・表示します。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        t5_kmeans = st.text_input(
            "クラスタ辞書 .npz",
            f"{root_dir}/patches/kmeans.npz",
            key="t5_kmeans",
        )
        t5_feat = st.text_input(
            "特徴量 .npz（ヒートマップ用、省略可）",
            f"{root_dir}/patches/patches.npz",
            key="t5_feat",
        )
        t5_gallery_out = st.text_input(
            "ギャラリー出力 PNG",
            f"{root_dir}/patches/parts_gallery.png",
            key="t5_gallery_out",
        )
        t5_heatmap_out = st.text_input(
            "ヒートマップ出力 PNG",
            f"{root_dir}/patches/parts_heatmap.png",
            key="t5_heatmap_out",
        )
    with col_b:
        t5_cols = st.number_input(
            "グリッド列数", 4, 32, 8, key="t5_cols"
        )
        t5_thumb = st.number_input(
            "サムネイルサイズ (px)", 32, 256, 96, key="t5_thumb"
        )
        t5_sdf_size = st.number_input(
            "SDF 画像サイズ (px)", 64, 1024, 256, key="t5_sdf_size"
        )
        t5_cmap = st.selectbox(
            "カラーマップ (ギャラリー)",
            ["RdBu_r", "bwr", "seismic", "coolwarm"],
            key="t5_cmap",
        )
        t5_hcmap = st.selectbox(
            "カラーマップ (ヒートマップ)",
            ["hot", "plasma", "inferno", "magma"],
            key="t5_hcmap",
        )

    if st.button("▶ 可視化実行", key="run_t5", type="primary"):
        kmeans_path_t5 = Path(t5_kmeans)
        if not kmeans_path_t5.exists():
            st.error(
                f"❌ クラスタ辞書ファイルが見つかりません: {kmeans_path_t5}"
            )
            st.stop()

        kmeans_data_t5 = _load_kmeans(kmeans_path_t5)
        gallery_out_t5 = Path(t5_gallery_out)
        gallery_out_t5.parent.mkdir(parents=True, exist_ok=True)

        with _capture_logs() as log_buf_t5:
            # --- Parts gallery -------------------------------------------
            with st.spinner("部品辞書ギャラリー生成中…"):
                try:
                    _parts_gallery(
                        kmeans_data_t5,
                        out_path=gallery_out_t5,
                        cols=int(t5_cols),
                        thumb_px=int(t5_thumb),
                        cmap=str(t5_cmap),
                    )
                except Exception as exc:
                    st.error(f"❌ ギャラリー生成エラー: {exc}")

            if gallery_out_t5.exists():
                st.subheader("部品辞書ギャラリー")
                st.image(str(gallery_out_t5), use_container_width=True)

            # --- Position heatmaps (optional) ----------------------------
            feat_path_t5 = Path(t5_feat) if t5_feat.strip() else None
            if feat_path_t5 and feat_path_t5.exists():
                heatmap_out_t5 = Path(t5_heatmap_out)
                heatmap_out_t5.parent.mkdir(parents=True, exist_ok=True)
                features_data_t5 = _load_features(feat_path_t5)

                with st.spinner("位置ヒートマップ生成中…"):
                    try:
                        _parts_heatmaps(
                            kmeans_data_t5,
                            features_data_t5,
                            out_path=heatmap_out_t5,
                            sdf_size=int(t5_sdf_size),
                            cols=int(t5_cols),
                            thumb_px=int(t5_thumb),
                            hcmap=str(t5_hcmap),
                        )
                    except Exception as exc:
                        st.error(f"❌ ヒートマップ生成エラー: {exc}")

                if heatmap_out_t5.exists():
                    st.subheader("位置ヒートマップ")
                    st.image(str(heatmap_out_t5), use_container_width=True)

        log_t5 = log_buf_t5.getvalue()
        if log_t5:
            with st.expander("ログ"):
                st.code(log_t5)

    # Preview existing results even without re-running
    st.markdown("---")
    st.subheader("既存の結果を表示")
    col_prev_a, col_prev_b = st.columns(2)
    with col_prev_a:
        existing_gallery = Path(t5_gallery_out)
        if existing_gallery.exists():
            st.markdown("**部品辞書ギャラリー**")
            st.image(str(existing_gallery), use_container_width=True)
    with col_prev_b:
        existing_heatmap = Path(t5_heatmap_out)
        if existing_heatmap.exists():
            st.markdown("**位置ヒートマップ**")
            st.image(str(existing_heatmap), use_container_width=True)
