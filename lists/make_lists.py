"""
make_lists.py
=============
Generate three character-list files under lists/:

  joyo.txt             – copy of ../data/joyo.txt (Joyo kanji, 1 char/line, UTF-8)
  jis_level2_kanji.txt – JIS X 0208 第1・第2水準 漢字 (CJK U+4E00–U+9FFF only)
  union_joyo_jis2.txt  – NFC-normalized, deduplicated, sorted union of the two lists

Usage:
    python lists/make_lists.py
    # or, from inside lists/:
    python make_lists.py
"""

import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent          # lists/
ROOT = HERE.parent                    # repository root
JOYO_SRC = ROOT / "data" / "joyo.txt"

OUT_JOYO    = HERE / "joyo.txt"
OUT_JIS2    = HERE / "jis_level2_kanji.txt"
OUT_UNION   = HERE / "union_joyo_jis2.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_list(path: Path, chars: list[str]) -> None:
    """Write one character per line, UTF-8, with a single trailing newline."""
    path.write_text("\n".join(chars) + "\n", encoding="utf-8")
    print(f"  wrote {len(chars)} chars → {path.relative_to(ROOT)}")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ---------------------------------------------------------------------------
# 1. joyo.txt  (copy from data/)
# ---------------------------------------------------------------------------

def build_joyo() -> list[str]:
    chars = [
        nfc(line.strip())
        for line in JOYO_SRC.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return chars


# ---------------------------------------------------------------------------
# 2. jis_level2_kanji.txt  (JIS X 0208 第1・第2水準 漢字)
# ---------------------------------------------------------------------------
# JIS X 0208 uses ISO-2022-JP encoding.
# A character at (row, col) is encoded as:
#   ESC $ B <row+0x20> <col+0x20> ESC ( B
# where row and col each run from 1 to 94.
# We keep only code points in the CJK Unified Ideographs block (U+4E00–U+9FFF).

_ESC = b"\x1b"
_CJK_START = 0x4E00
_CJK_END   = 0x9FFF


def _jis_char(row: int, col: int) -> str | None:
    """Return the Unicode character for JIS X 0208 (row, col), or None."""
    b = _ESC + b"$B" + bytes([row + 0x20, col + 0x20]) + _ESC + b"(B"
    try:
        ch = b.decode("iso2022_jp")
        if len(ch) == 1 and _CJK_START <= ord(ch) <= _CJK_END:
            return ch
    except (UnicodeDecodeError, ValueError):
        pass
    return None


def build_jis2() -> list[str]:
    seen: set[str] = set()
    chars: list[str] = []
    for row in range(1, 95):
        for col in range(1, 95):
            ch = _jis_char(row, col)
            if ch is not None:
                nch = nfc(ch)
                if nch not in seen:
                    seen.add(nch)
                    chars.append(nch)
    return chars


# ---------------------------------------------------------------------------
# 3. union_joyo_jis2.txt
# ---------------------------------------------------------------------------

def build_union(joyo: list[str], jis2: list[str]) -> list[str]:
    combined = {nfc(c) for c in joyo} | {nfc(c) for c in jis2}
    return sorted(combined)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Building character lists …")

    joyo = build_joyo()
    write_list(OUT_JOYO, joyo)

    jis2 = build_jis2()
    write_list(OUT_JIS2, jis2)

    union = build_union(joyo, jis2)
    write_list(OUT_UNION, union)

    print("Done.")


if __name__ == "__main__":
    main()
