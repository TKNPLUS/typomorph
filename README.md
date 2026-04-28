# typomorph

漢字グリフの形状解析・パーツ抽出・モーフィングのための研究・作品制作パイプラインです。

---

## ディレクトリ構成

```
typomorph/
├── data/
│   └── joyo.txt               # 常用漢字の原典テキスト（UTF-8、1行1文字）
├── lists/
│   ├── make_lists.py          # 文字リスト生成スクリプト
│   ├── joyo.txt               # 常用漢字リスト（生成物）
│   ├── jis_level2_kanji.txt   # JIS X 0208 第1・第2水準 漢字（生成物）
│   └── union_joyo_jis2.txt    # 常用∪JIS2 の和集合（生成物）
├── scripts/
│   ├── render_png.py          # 文字 → 正規化PNG レンダリングスクリプト
│   ├── make_sdf.py            # PNG → SDF（.npy）生成スクリプト
│   ├── viz_sdf.py             # SDF（.npy）可視化スクリプト（単体表示・ギャラリー）
│   ├── patch_extractor.py     # SDF → 局所パッチ抽出・特徴量保存（.npz）
│   ├── patch_kmeans.py        # パッチ特徴量 → PCA + k-means クラスタ辞書（.npz）
│   ├── viz_parts.py           # クラスタ辞書の可視化（部品ギャラリー・位置ヒートマップ）
│   └── demo_parts.py          # 部品辞書の探索・応用デモ（モーフィング・復元・統計）
├── app.py                     # Streamlit GUI（全パイプラインを 1 画面で操作）
├── requirements.txt           # Python 依存パッケージ
├── Dockerfile                 # Docker イメージ定義
└── README.md
```

---

## Docker を使ったセットアップ・実行

### 前提

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) がインストール済みであること（Windows の場合 WSL2 バックエンド推奨）

### ① イメージのビルド

**Windows PowerShell:**
```powershell
docker build -t typomorph .
```

**Git Bash / WSL:**
```bash
docker build -t typomorph .
```

---

### ② フォントの確認

コンテナを起動してフォントが正しくインストールされているか確認します。

**Windows PowerShell:**
```powershell
docker run --rm typomorph fc-list | Select-String -Pattern "noto" -CaseSensitive:$false
```

**Git Bash:**
```bash
docker run --rm typomorph fc-list | grep -i noto
```

出力例：
```
/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc: Noto Sans CJK JP:style=Regular
```

---

### ③ PNG レンダリングの実行

カレントディレクトリをコンテナの `/work` にマウントして実行します。

**Windows PowerShell:**
```powershell
docker run --rm -v ${PWD}:/work typomorph `
    python scripts/render_png.py `
    --list lists/joyo.txt `
    --out  out/png `
    --font "Noto Sans CJK JP"
```

**Git Bash:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/render_png.py \
    --list lists/joyo.txt \
    --out  out/png \
    --font "Noto Sans CJK JP"
```

**Windows コマンドプロンプト (cmd.exe):**
```cmd
docker run --rm -v %cd%:/work typomorph ^
    python scripts/render_png.py ^
    --list lists/joyo.txt ^
    --out  out/png ^
    --font "Noto Sans CJK JP"
```

出力は `out/png/` ディレクトリに `U+4E00.png` のようなファイル名（Unicode コードポイント）で保存されます。

---

### render_png.py オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--list` | （必須） | 1行1文字のテキストファイルパス |
| `--out` | （必須） | PNG 出力ディレクトリ |
| `--font` | （必須） | fontconfig フォントファミリー名（例: `"Noto Sans CJK JP"`） |
| `--size` | `256` | 出力画像サイズ（ピクセル） |
| `--margin` | `0.10` | 余白率（各辺、0.10 = 10%） |
| `--skip-existing` | `false` | 既存ファイルをスキップする |

#### `--skip-existing` の使用例（差分のみ更新）

```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/render_png.py \
    --list lists/joyo.txt \
    --out  out/png \
    --font "Noto Sans CJK JP" \
    --skip-existing
```

---

### ④ SDF 生成の実行

`out/png/` の PNG ファイルをもとに Signed Distance Field（符号付き距離場）を生成します。

**Windows PowerShell:**
```powershell
docker run --rm -v ${PWD}:/work typomorph `
    python scripts/make_sdf.py `
    --list lists/joyo.txt `
    --png  out/png `
    --out  out/sdf
```

**Git Bash:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/make_sdf.py \
    --list lists/joyo.txt \
    --png  out/png \
    --out  out/sdf
```

**Windows コマンドプロンプト (cmd.exe):**
```cmd
docker run --rm -v %cd%:/work typomorph ^
    python scripts/make_sdf.py ^
    --list lists/joyo.txt ^
    --png  out/png ^
    --out  out/sdf
```

出力は `out/sdf/` ディレクトリに `U+4E00.npy` のようなファイル名で保存されます。  
各ファイルは **float32 の 256×256 numpy 配列**で、距離はピクセル単位です。  
符号の定義：**内側（インク）が負、外側（背景）が正**、値域は `[-32, 32]` にクリップ。

---

### make_sdf.py オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--list` | （必須） | 1行1文字のテキストファイルパス |
| `--png` | （必須） | 入力 PNG ディレクトリ（例: `out/png`） |
| `--out` | （必須） | SDF 出力ディレクトリ（例: `out/sdf`） |
| `--clip` | `32` | 距離クリップ半径（ピクセル） |
| `--threshold` | `128` | 二値化しきい値（この値未満がインク/内側） |
| `--workers` | `1` | 並列ワーカープロセス数（1 = 直列） |
| `--skip-existing` | `false` | 既存ファイルをスキップする |

#### 並列処理・既存スキップの使用例

```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/make_sdf.py \
    --list lists/joyo.txt \
    --png  out/png \
    --out  out/sdf \
    --workers 4 \
    --skip-existing
```

---

## SDFの見方（可視化ガイド）

> **ポイント：** 中央付近に **0等値線（白いライン）** が現れ、それを跨いで青（内側・インク）と赤（外側・背景）に分かれるのが正常なSDFです。

### SDFが「靄（もや）状」に見えるのは正常

SDF（符号付き距離場）は **輪郭からの距離** を各ピクセルに格納した配列です。  
そのため、`numpy.load()` 後に直接 `imshow()` すると「全体がふわっとグレーに満ちている」ように見えますが、これは正しい挙動です。

| 状態 | 意味 |
|---|---|
| 全体が滑らかなグラデーション（靄状） | ✅ 正常（SDF の本来の性質） |
| 輪郭付近に中央を横切る0等値線が見える | ✅ 正常 |
| 全ピクセルがほぼ同じ値（真っ黒 / 真っ白）で輪郭が見えない | ⚠️ 変換ミスの可能性 |

---

### ⑤ SDF の可視化（1文字）

`scripts/viz_sdf.py` を使うと、SDFを**発散型カラーマップ（内側=青、外側=赤）** と **0等値線（白）** で表示できます。

**単体表示（インタラクティブ）:**
```bash
python scripts/viz_sdf.py out/sdf/U+4E00.npy
```

**PNG に保存:**
```bash
python scripts/viz_sdf.py out/sdf/U+4E00.npy --out preview.png
```

**Docker を使う場合:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/viz_sdf.py out/sdf/U+4E00.npy --out preview.png
```

---

### ⑥ SDF ギャラリー（複数文字を一覧表示）

`--gallery` オプションを使うと、ディレクトリ内の全 `.npy` ファイルをサムネイル一覧 PNG に書き出せます。

```bash
python scripts/viz_sdf.py --gallery out/sdf/ --out gallery.png
```

**文字リストで絞り込み・順序を指定する場合:**
```bash
python scripts/viz_sdf.py --gallery out/sdf/ --list lists/joyo.txt --out gallery.png
```

**カラム数とサムネサイズを調整する場合:**
```bash
python scripts/viz_sdf.py --gallery out/sdf/ --cols 20 --thumb 64 --out gallery.png
```

**Docker を使う場合:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/viz_sdf.py --gallery out/sdf/ --list lists/joyo.txt --out gallery.png
```

---

### viz_sdf.py オプション一覧

**単体表示モード（positional argument に .npy ファイルを指定）**

| オプション | デフォルト | 説明 |
|---|---|---|
| `file` | （必須） | .npy SDF ファイルパス |
| `--out` | なし（インタラクティブ表示） | 出力ファイルパス（PNG / PDF / SVG）|
| `--clip` | auto | カラー軸の対称上限（ピクセル）|
| `--no-contour` | false | 0等値線を非表示にする |
| `--cmap` | `RdBu_r` | Matplotlib カラーマップ名 |
| `--title` | ファイルステム | 図のタイトル |

**ギャラリーモード（`--gallery DIR` を指定）**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--gallery` | （必須） | .npy ファイルが入ったディレクトリ |
| `--list` | なし（全ファイル） | 文字リスト .txt（絞り込み・順序指定）|
| `--out` | `<sdf_dir>/sdf_gallery.png` | 出力 PNG パス |
| `--cols` | `16` | グリッドの列数 |
| `--thumb` | `48` | サムネイルサイズ（ピクセル）|
| `--cmap` | `RdBu_r` | Matplotlib カラーマップ名 |

---

### 輪郭線だけを確認したい場合（0-crossing 抽出）

SDF が 0 を跨ぐ箇所だけを表示すれば、元の字形に近いシルエットを確認できます。

```python
import numpy as np
import matplotlib.pyplot as plt

sdf = np.load("out/sdf/U+4E00.npy")
fig, ax = plt.subplots(figsize=(4, 4))
ax.contour(sdf, levels=[0.0], colors="black", linewidths=1.5)
ax.set_aspect("equal")
ax.invert_yaxis()
ax.axis("off")
plt.tight_layout()
plt.show()
```

---


`lists/joyo.txt` は `data/joyo.txt`（文化庁常用漢字表を参照）をもとに生成されます。  
JIS X 0208 第1・第2水準リストや和集合を再生成するには：

```bash
docker run --rm -v "$(pwd)":/work typomorph python lists/make_lists.py
```

出典：文化庁「常用漢字表（平成22年11月30日内閣告示）」  
<https://www.bunka.go.jp/kokugo_nihongo/sisaku/joho/joho/kijun/naikaku/pdf/joyokanjihyo_20101130.pdf>

---

## ローカル環境（Docker なし）での実行

Python 3.11+ と fontconfig が利用可能な環境（Linux / WSL2 推奨）では Docker なしでも動作します。

```bash
pip install -r requirements.txt
python scripts/render_png.py --list lists/joyo.txt --out out/png --font "Noto Sans CJK JP"
python scripts/make_sdf.py   --list lists/joyo.txt --png out/png  --out out/sdf
```

fontconfig が未インストールの場合：

```bash
# Ubuntu / Debian / WSL2
sudo apt install fonts-noto-cjk fontconfig
fc-cache -fv
```

---

## GUI（Streamlit）での操作

CLI スクリプトを 1 つの Web UI から順番に実行できます。  
① PNG レンダリング → ② SDF 生成 → ③ パッチ抽出 → ④ クラスタリング → ⑤ 可視化  
という 5 ステップすべてをタブ切り替えでコントロールできます。

---

### 推奨環境

| 項目 | 要件 |
|---|---|
| Python | 3.11 以上 |
| OS | Linux / WSL2 / macOS（Windows は WSL2 推奨） |
| フォント | Noto Sans CJK JP（`apt install fonts-noto-cjk`） |
| fontconfig | `apt install fontconfig` |

---

### 依存パッケージ

`requirements.txt` に追加された主な依存：

| パッケージ | バージョン | 用途 |
|---|---|---|
| `streamlit` | >=1.35,<2 | Web GUI フレームワーク |
| `numpy` | >=2.2,<3 | 数値計算 |
| `pillow` | >=11.0,<13 | PNG 読み書き |
| `scipy` | >=1.15,<2 | SDF 距離変換 |
| `scikit-learn` | >=1.6,<2 | PCA・k-means |
| `matplotlib` | >=3.9,<4 | 可視化・ギャラリー生成 |
| `tqdm` | >=4.66,<5 | プログレスバー（CLI） |

インストール：

```bash
pip install -r requirements.txt
```

---

### ローカルでの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動で開きます。

---

### Docker での起動

**Git Bash / WSL:**
```bash
docker run --rm -p 8501:8501 -v "$(pwd)":/work typomorph \
    streamlit run app.py --server.address 0.0.0.0
```

**Windows PowerShell:**
```powershell
docker run --rm -p 8501:8501 -v ${PWD}:/work typomorph `
    streamlit run app.py --server.address 0.0.0.0
```

起動後、ブラウザで `http://localhost:8501` を開いてください。

---

### GUI の使い方

サイドバーの **「出力ルートディレクトリ」** でデータ保存先を指定し、  
各タブを順番に操作します。

| タブ | 対応 CLI スクリプト | 主なパラメータ |
|---|---|---|
| ① PNG レンダリング | `render_png.py` | 文字リスト・フォント名・解像度・マージン |
| ② SDF 生成 | `make_sdf.py` | クリップ距離・2値化しきい値 |
| ③ パッチ抽出 | `patch_extractor.py` | パッチサイズ・境界パッチ数・マージン幅 |
| ④ クラスタリング | `patch_kmeans.py` | クラスタ数 k・PCA 次元数・乱数シード |
| ⑤ 可視化 | `viz_parts.py` | グリッド列数・サムネイルサイズ・カラーマップ |

- **▶ ボタン**を押すと処理が実行され、プログレスバーで進捗が表示されます。
- 処理完了後、結果画像（ギャラリー・ヒートマップ）がページ内にサムネイル表示されます。
- サイドバーの **「パイプライン状態」** で各ステージの出力ファイル有無を確認できます。

---

SDFの可視化・正常性確認が済んだら、次のステップとして「部首っぽいパーツ断片化」を行います。  
SDFから局所パッチを切り出し、PCAで次元圧縮したあとにk-meansでクラスタリングすることで、  
**"部首候補パーツの辞書"** を自動生成できます。

```
SDF (.npy)
  └─ patch_extractor.py ─→ patches.npz（特徴量行列）
       └─ patch_kmeans.py ─→ kmeans.npz（クラスタ辞書）
            └─ viz_parts.py ─→ parts_gallery.png / parts_heatmap.png
```

### ⑦ パッチ抽出（patch_extractor.py）

各SDF画像から「SDF=0 付近（輪郭近傍）」のパッチを切り出します。  
各パッチは flatten されて特徴量ベクトルとして `.npz` に保存されます。

```bash
python scripts/patch_extractor.py \
    --sdf  out/sdf \
    --out  out/patches/patches.npz
```

**Docker を使う場合:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/patch_extractor.py \
    --sdf  out/sdf \
    --out  out/patches/patches.npz
```

**主なオプション:**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--sdf` | （必須） | SDF `.npy` ファイルのディレクトリ |
| `--out` | （必須） | 出力 `.npz` ファイルパス |
| `--list` | なし（全ファイル） | 文字リスト `.txt` で対象を絞る |
| `--patch-size` | `64` | パッチの一辺サイズ（ピクセル） |
| `--border-patches` | `20` | 1文字あたりの輪郭近傍パッチ数 |
| `--random-patches` | `0` | 1文字あたりのランダムパッチ数 |
| `--border-margin` | `8` | 「輪郭近傍」と判定する SDF 閾値（ピクセル） |
| `--seed` | `42` | 乱数シード |

---

### ⑧ PCA + k-means クラスタリング（patch_kmeans.py）

抽出したパッチ特徴量を PCA で圧縮し、k-means でクラスタリングします。  
各クラスタが「部首・部品の候補」に対応します。

```bash
python scripts/patch_kmeans.py \
    --features out/patches/patches.npz \
    --out      out/patches/kmeans.npz
```

**Docker を使う場合:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/patch_kmeans.py \
    --features out/patches/patches.npz \
    --out      out/patches/kmeans.npz
```

**主なオプション:**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--features` | （必須） | `patch_extractor.py` が出力した `.npz` ファイル |
| `--out` | （必須） | 出力クラスタ辞書 `.npz` ファイルパス |
| `--clusters` | `64` | k-means のクラスタ数（部品数） |
| `--pca` | `64` | PCA の次元数 |
| `--seed` | `42` | 乱数シード |
| `--max-iter` | `300` | k-means 最大イテレーション数 |
| `--n-init` | `10` | k-means 初期化試行回数 |

---

### ⑨ 部品辞書の可視化（viz_parts.py）

クラスタ辞書（代表パッチ一覧・位置ヒートマップ）を PNG に出力します。

**部品ギャラリー（代表パッチグリッド）:**
```bash
python scripts/viz_parts.py \
    --kmeans out/patches/kmeans.npz \
    --out    out/patches/parts_gallery.png
```

**部品ギャラリー + 出現位置ヒートマップ:**
```bash
python scripts/viz_parts.py \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/parts_gallery.png \
    --heatmap  out/patches/parts_heatmap.png
```

**Docker を使う場合:**
```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/viz_parts.py \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/parts_gallery.png \
    --heatmap  out/patches/parts_heatmap.png
```

**主なオプション:**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--kmeans` | （必須） | `patch_kmeans.py` が出力した `.npz` ファイル |
| `--features` | なし | `patch_extractor.py` の `.npz`（ヒートマップに必要） |
| `--out` | `parts_gallery.png` | ギャラリー PNG 出力パス |
| `--heatmap` | なし（省略可） | 位置ヒートマップ PNG 出力パス（`--features` 必須） |
| `--sdf-size` | `256` | 元 SDF 画像の一辺ピクセル数 |
| `--cols` | `8` | グリッド列数 |
| `--thumb` | `96` | サムネイルサイズ（ピクセル） |
| `--cmap` | `RdBu_r` | パッチ表示用カラーマップ |
| `--hcmap` | `hot` | ヒートマップ用カラーマップ |

---

### パーツ断片化の意義

このフェーズにより以下が実現できます：

| 用途 | 内容 |
|---|---|
| **研究用途** | クラスタごとの出現位置分布・出現頻度・代表形状を定量化 |
| **作品用途** | クラスタパッチを組み合わせることで新たな文字の"合成"が可能 |
| **次フェーズへの橋渡し** | 復元誤差・クラスタ間モーフィング・パーツ置換実験 |

> **ポイント：** 部首の自動分類ではなく「データ駆動な形状断片化」が行われます。  
> クラスタが必ずしも人間の定義する部首と一致するとは限りませんが、  
> 統計的に繰り返し出現する形状パターンを捉えた辞書が得られます。

---

## 成果物整理と可視化図説

### 生成画像の意義

`parts_gallery.png` と `parts_heatmap.png` はそれぞれ以下の情報を可視化した成果物です。

| ファイル | 内容 | 研究・作品上の意義 |
|---|---|---|
| `parts_gallery.png` | クラスタごとの代表パッチ一覧（SDF カラーマップ＋等値線） | データ駆動で発見された「部首様パーツ辞書」の全体像を一望できる。論文・発表の **Figure** として直接使用可能 |
| `parts_heatmap.png` | クラスタごとのパッチ出現位置の 2-D ヒストグラム | 各パーツが文字のどの位置（左辺・上部・中央など）に集中して現れるかを示す。位置的役割の統計的解釈に有用 |

### 研究用図説（キャプション案）

**日本語キャプション例:**

```
図X. データ駆動な部首様パーツ辞書（64クラスタ，パッチサイズ64px）
各セルはクラスタの代表パッチを SDF カラーマップ（青=インク内側，赤=外側，白=輪郭）で表示し，
括弧内はそのクラスタへ割り当てられたパッチ総数を示す。
```

```
図Y. クラスタ別パッチ出現位置ヒートマップ（64クラスタ）
各マップは対応するクラスタのパッチ中心が 256×256 グリッド上のどの位置に集中して現れるかを
2-D ヒストグラム（ビン数 32×32）で表したもの。輝度が高いほど出現頻度が高い。
```

**英語キャプション例:**

```
Figure X.  Data-driven radical-like parts dictionary (64 clusters, 64 px patches).
Each cell shows the representative patch of a cluster rendered as an SDF colormap
(blue = inside/ink, red = outside, white = outline).  Numbers in parentheses denote
the cluster population.
```

```
Figure Y.  Per-cluster patch position heatmaps (64 clusters).
Each map is a 2-D histogram (32×32 bins) of patch centre coordinates within
the 256×256 SDF grid, aggregated over all characters.  Brighter values indicate
higher occurrence frequency.
```

### LaTeX 図挿入サンプル

```latex
\begin{figure}[tbp]
  \centering
  \includegraphics[width=\linewidth]{figures/parts_gallery.png}
  \caption{Data-driven radical-like parts dictionary (64 clusters, 64\,px patches).
           Each cell shows the representative SDF patch of a cluster;
           blue regions indicate ink (negative SDF), red indicates background
           (positive SDF), and white contours mark the glyph outline ($d=0$).
           Numbers in parentheses show the cluster population.}
  \label{fig:parts_gallery}
\end{figure}

\begin{figure}[tbp]
  \centering
  \includegraphics[width=\linewidth]{figures/parts_heatmap.png}
  \caption{Patch position heatmaps for all 64 clusters.
           Each map is a 2-D histogram of patch centre locations within
           the $256\times256$ SDF grid, aggregated across the entire character set.
           Brighter colours indicate higher occurrence frequency,
           revealing the preferred spatial role of each part
           (e.g.\ left-side radical vs.\ top component).}
  \label{fig:parts_heatmap}
\end{figure}
```

---

## 今後の推奨ステップ

### ⑩ 復元性能評価（定量評価）

パーツ辞書でどれだけ元の SDF を再現できるかを測定します。  
各文字の SDF を「辞書の最近傍パッチで埋め戻す」ことで再構成 SDF を作り、  
元 SDF との差分（MSE・PSNR など）を算出します。

```bash
python scripts/demo_parts.py reconstruct \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --sdf      out/sdf \
    --out      out/patches/reconstruction
```

| 指標 | 意味 |
|---|---|
| **MSE (Mean Squared Error)** | 再構成精度（低いほど良い） |
| **PSNR** | ピーク信号対雑音比（高いほど良い） |
| **Coverage rate** | 元 SDF の輪郭ピクセルのうちパッチで覆われた割合 |

### ⑪ 部首-文字分解タスク（Radical Decomposition）

クラスタラベル列を文字ごとに集計すると、  
「この文字はクラスタ X・Y・Z から構成される」という**部首分解ベクトル**が得られます。  
これを使って：

- 同じ部首パーツを多く共有する文字をクラスタ化（意味的な類似文字検索）
- 「部首ベクトル」の演算で新しい字形を設計（ベクトル算術）

```bash
python scripts/demo_parts.py decompose \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/char_vectors.csv
```

### ⑫ 応用デモ：パーツ変換・生成アート

`demo_parts.py` の `morph` サブコマンドで、2 つのクラスタ代表パッチ間の  
線形補間（モーフィング）アニメーションを生成できます。

```bash
# クラスタ 3 → クラスタ 27 の 8 ステップモーフィング
python scripts/demo_parts.py morph \
    --kmeans out/patches/kmeans.npz \
    --from 3 --to 27 --steps 8 \
    --out out/patches/morph_3_27.png
```

また `gallery-stats` サブコマンドで CSV 統計を出力し、  
各クラスタの出現重心・分散なども確認できます。

```bash
python scripts/demo_parts.py gallery-stats \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/cluster_stats.csv
```

---

## 付録：可視化デモスクリプト（demo_parts.py）

`scripts/demo_parts.py` は部品辞書を対話的に探索・応用するためのスタンドアロンデモです。  
以下の 5 つのサブコマンドを持ちます。

| サブコマンド | 説明 |
|---|---|
| `show-patch` | 指定したクラスタ番号の代表パッチを表示・保存 |
| `morph` | 2 クラスタ間の線形補間パッチ列を画像として保存 |
| `reconstruct` | SDF をパーツ辞書で再構成し元画像との差分を可視化 |
| `gallery-stats` | クラスタごとの統計（件数・重心・分散）を CSV 出力 |
| `decompose` | 文字ごとのクラスタ割当ベクトルを CSV 出力 |

### インストール済み環境での使い方

```bash
# 代表パッチをファイルに保存（クラスタ番号 5）
python scripts/demo_parts.py show-patch \
    --kmeans out/patches/kmeans.npz \
    --cluster 5 \
    --out out/patches/patch_5.png

# 2 クラスタ間モーフィング（8 ステップ）
python scripts/demo_parts.py morph \
    --kmeans out/patches/kmeans.npz \
    --from 3 --to 27 --steps 8 \
    --out out/patches/morph_3_27.png

# クラスタ統計 CSV
python scripts/demo_parts.py gallery-stats \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/cluster_stats.csv

# 文字ごとのクラスタ割当ベクトル CSV
python scripts/demo_parts.py decompose \
    --kmeans   out/patches/kmeans.npz \
    --features out/patches/patches.npz \
    --out      out/patches/char_vectors.csv
```

### Docker を使う場合

```bash
docker run --rm -v "$(pwd)":/work typomorph \
    python scripts/demo_parts.py morph \
    --kmeans out/patches/kmeans.npz \
    --from 3 --to 27 --steps 8 \
    --out out/patches/morph_3_27.png
```

---

## 付録：出力ファイル仕様

### `.npy` (SDF 単体ファイル)

| 項目 | 仕様 |
|---|---|
| dtype | `float32` |
| shape | `(H, W)` — デフォルト `(256, 256)` |
| 値域 | `[-clip, clip]` — デフォルト `[-32.0, 32.0]` ピクセル単位 |
| 符号 | 負 = インク内側、正 = 背景、0 = 輪郭 |
| ファイル名 | `U+<XXXX>.npy`（Unicode コードポイント大文字 4〜5 桁） |

### `patches.npz` (パッチ特徴量ファイル)

`patch_extractor.py` が出力する `.npz` の配列仕様:

| キー | shape | dtype | 説明 |
|---|---|---|---|
| `patches` | `(N, patch_size*patch_size)` | float32 | flatten されたパッチ特徴量 |
| `positions` | `(N, 3)` | int32 | `[file_idx, row, col]`（パッチ左上座標） |
| `file_ids` | `(F,)` | unicode str | ファイル識別子（コードポイント文字列）の配列 |
| `patch_size` | scalar | int | パッチ一辺サイズ（ピクセル） |

### `kmeans.npz` (クラスタ辞書ファイル)

`patch_kmeans.py` が出力する `.npz` の配列仕様:

| キー | shape | dtype | 説明 |
|---|---|---|---|
| `rep_patches` | `(k, patch_size, patch_size)` | float32 | 各クラスタの代表パッチ（クラスタ重心を元空間に逆変換） |
| `labels` | `(N,)` | int32 | 全パッチのクラスタラベル |
| `centers` | `(k, pca_dim)` | float32 | PCA 空間でのクラスタ重心 |
| `pca_components` | `(pca_dim, patch_size*patch_size)` | float32 | PCA 主成分行列 |
| `pca_mean` | `(patch_size*patch_size,)` | float32 | PCA 平均ベクトル |
| `n_clusters` | scalar | int | クラスタ数 k |
| `patch_size` | scalar | int | パッチ一辺サイズ（ピクセル） |

### PNG 出力ファイル

| ファイル | 生成スクリプト | 説明 |
|---|---|---|
| `out/png/U+<XXXX>.png` | `render_png.py` | グレースケール PNG（白背景・黒文字） |
| `out/patches/parts_gallery.png` | `viz_parts.py` | 部品辞書ギャラリー（クラスタ代表パッチ一覧） |
| `out/patches/parts_heatmap.png` | `viz_parts.py` | 出現位置ヒートマップ一覧 |
| `out/patches/morph_*.png` | `demo_parts.py` | クラスタ間モーフィング画像 |
