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
│   └── render_png.py     # 文字 → 正規化PNG レンダリングスクリプト
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

## 文字リストの生成

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
```

fontconfig が未インストールの場合：

```bash
# Ubuntu / Debian / WSL2
sudo apt install fonts-noto-cjk fontconfig
fc-cache -fv
```
