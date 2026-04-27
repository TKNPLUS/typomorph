# typomorph

漢字グリフの形状解析・パーツ抽出・モーフィングのための研究・作品制作パイプラインです。

---

## ディレクトリ構成

```
typomorph/
├── data/
│   └── joyo.txt          # 常用漢字の原典テキスト（UTF-8、1行1文字）
├── lists/
│   ├── make_lists.py     # 文字リスト生成スクリプト
│   ├── joyo.txt          # 常用漢字リスト（生成物）
│   ├── jis_level2_kanji.txt   # JIS X 0208 第1・第2水準 漢字（生成物）
│   └── union_joyo_jis2.txt    # 常用∪JIS2 の和集合（生成物）
├── scripts/
│   ├── render_png.py     # 文字 → 正規化PNG レンダリングスクリプト
│   ├── make_sdf.py       # PNG → SDF（.npy）生成スクリプト
│   └── viz_sdf.py        # SDF（.npy）可視化スクリプト（単体表示・ギャラリー）
├── requirements.txt      # Python 依存パッケージ
├── Dockerfile            # Docker イメージ定義
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
