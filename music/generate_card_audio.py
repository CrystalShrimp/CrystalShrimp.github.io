"""Generate TTS audio for every word and example sentence in word_card.xlsx.

Usage:
    python generate_card_audio.py [folder]

`folder` defaults to the current directory. Reads `word_card.xlsx` from the
folder and writes:
    audio/words/<slug>.mp3        (per word)
    audio/examples/<hash>.mp3     (per unique example sentence)

Voice: de-DE-KatjaNeural, rate -10%. Existing files are skipped.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import edge_tts
import openpyxl

VOICE = "de-DE-KatjaNeural"
RATE = "-10%"


def slug(word: str) -> str:
    s = word.lower().strip()
    s = re.sub(r"[^a-zäöüß\-]", "", s)
    return s


def example_hash(text: str) -> str:
    return hashlib.sha1(text.lower().encode("utf-8")).hexdigest()[:12]


def read_rows(xlsx: Path):
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        cells = [str(c).strip() if c is not None else "" for c in row]
        while len(cells) < 5:
            cells.append("")
        word, _ipa, _en, ex_de, _zh = cells[:5]
        if word:
            rows.append((word, ex_de))
    return rows


async def synth(text: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 100:
        return False
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(dest))
    return True


async def main():
    folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    xlsx = folder / "word_card.xlsx"
    if not xlsx.exists():
        print(f"[error] {xlsx} not found.", file=sys.stderr)
        sys.exit(1)

    words_dir = folder / "audio" / "words"
    ex_dir = folder / "audio" / "examples"
    words_dir.mkdir(parents=True, exist_ok=True)
    ex_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(xlsx)
    print(f"[info] {folder.name}: {len(rows)} rows in word_card.xlsx")

    word_tasks: list[tuple[str, Path]] = []
    seen_words: set[str] = set()
    ex_tasks: list[tuple[str, Path]] = []
    seen_ex: set[str] = set()
    for word, ex_de in rows:
        wslug = slug(word)
        if wslug and wslug not in seen_words:
            seen_words.add(wslug)
            word_tasks.append((word, words_dir / f"{wslug}.mp3"))
        if ex_de:
            eh = example_hash(ex_de)
            if eh not in seen_ex:
                seen_ex.add(eh)
                ex_tasks.append((ex_de, ex_dir / f"{eh}.mp3"))

    print(f"[info] {folder.name}: {len(word_tasks)} unique words, {len(ex_tasks)} unique example sentences")

    sem = asyncio.Semaphore(8)

    async def run_one(text: str, dest: Path, label: str):
        async with sem:
            try:
                made = await synth(text, dest)
            except Exception as e:
                print(f"[err] {label} {dest.name}: {e}", file=sys.stderr)
                return
            print(f"[{'+' if made else '.'}] {label}: {dest.name}")

    print("[info] word audio...")
    await asyncio.gather(*[run_one(t, d, "word") for t, d in word_tasks])
    print("[info] example audio...")
    await asyncio.gather(*[run_one(t, d, "ex") for t, d in ex_tasks])
    print(f"[done] {folder.name}: words={len(list(words_dir.glob('*.mp3')))}, examples={len(list(ex_dir.glob('*.mp3')))}")


if __name__ == "__main__":
    asyncio.run(main())
