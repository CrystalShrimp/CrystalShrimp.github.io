"""Generate TTS audio for every line and unique word in lyric.md (or lyrics.md).

Usage:
    python generate_tts.py [folder]

`folder` defaults to the current directory. Looks for `lyrics.md`, falling back
to `lyric.md`. Outputs into `<folder>/audio/`:
    audio/sentences/<si>_<li>.mp3    one clip per lyric line
    audio/words/<slug>.mp3           one clip per unique word
    audio/index.json                 data file
    audio_index.js                   JS wrapper loaded by index.html

Voice: de-DE-KatjaNeural, rate -10%. Existing files are skipped.

Lyrics parser is liberal: accepts `##` or `###` section headers, ignores
`---` separators, `# title` lines, `【...】` Chinese section labels, and
`[A]` / `[B]` / `[Duet]` speaker markers.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import edge_tts

VOICE = "de-DE-KatjaNeural"
RATE = "-10%"
_CJK = re.compile(r"[一-龥]")
_BRACKET_ONLY = re.compile(r"^\[[A-Za-z0-9À-ÿ &\-]+\]$")


def slug(word: str) -> str:
    s = word.lower().strip()
    s = re.sub(r"[^a-zäöüß\-]", "", s)
    return s


def parse_lyrics(text: str):
    sections = []
    current = None
    pending_de = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "---":
            # separator — flush pending, but keep current section
            if pending_de is not None and current is not None:
                current["lines"].append({"de": pending_de, "zh": "", "en": ""})
                pending_de = None
            continue
        if line.startswith("# ") and not line.startswith("## "):
            # H1 song title
            continue
        if line.startswith("## ") or line.startswith("### "):
            if pending_de is not None and current is not None:
                current["lines"].append({"de": pending_de, "zh": "", "en": ""})
                pending_de = None
            name = re.sub(r"^#+\s+", "", line).strip()
            # Strip enclosing [ ] if present
            name = re.sub(r"^\[(.+)\]$", r"\1", name).strip()
            current = {"name": name, "subtitle": "", "lines": []}
            sections.append(current)
            continue
        if line.startswith("【") and line.endswith("】"):
            # Chinese section subtitle
            if current is not None:
                current["subtitle"] = line[1:-1].strip()
            continue
        if _BRACKET_ONLY.match(line):
            # Speaker marker like [A] / [B] / [Duet] — skip
            continue
        if line.lower().startswith(("en:", "en：", "[en]")):
            en_text = re.sub(r"^(en:|en：|\[en\])\s*", "", line, flags=re.I).strip()
            if current is not None and current["lines"]:
                current["lines"][-1]["en"] = en_text
            continue
        if _CJK.search(line):
            if pending_de is not None and current is not None:
                current["lines"].append({"de": pending_de, "zh": line, "en": ""})
                pending_de = None
        else:
            if pending_de is not None and current is not None:
                current["lines"].append({"de": pending_de, "zh": "", "en": ""})
            pending_de = line
    if pending_de is not None and current is not None:
        current["lines"].append({"de": pending_de, "zh": "", "en": ""})
    return sections


async def synth(text: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 100:
        return False
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(dest))
    return True


async def main():
    folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    lyrics_file = folder / "lyrics.md"
    if not lyrics_file.exists():
        lyrics_file = folder / "lyric.md"
    if not lyrics_file.exists():
        print(f"[error] no lyrics.md/lyric.md in {folder}", file=sys.stderr)
        sys.exit(1)

    text = lyrics_file.read_text(encoding="utf-8")
    sections = parse_lyrics(text)

    words_dir = folder / "audio" / "words"
    sent_dir = folder / "audio" / "sentences"
    words_dir.mkdir(parents=True, exist_ok=True)
    sent_dir.mkdir(parents=True, exist_ok=True)

    # Words: collect unique by lowercase
    word_seen: set[str] = set()
    word_tasks: list[tuple[str, Path]] = []
    for sec in sections:
        for ln in sec["lines"]:
            for tok in ln["de"].split():
                w = re.sub(r"[.,!?;:\"„“()¿¡…?]+", "", tok).strip()
                if not w:
                    continue
                key = w.lower()
                if key in word_seen:
                    continue
                word_seen.add(key)
                word_tasks.append((w, words_dir / f"{slug(w)}.mp3"))

    # Sentences: one file per line
    sent_records = []
    sent_tasks: list[tuple[str, Path]] = []
    for si, sec in enumerate(sections):
        for li, ln in enumerate(sec["lines"]):
            sid = f"{si:02d}_{li:02d}"
            file_rel = f"audio/sentences/{sid}.mp3"
            sent_records.append({
                "id": f"{si}-{li}",
                "file": file_rel,
                "de": ln["de"],
                "zh": ln["zh"],
                "en": ln.get("en", ""),
            })
            sent_tasks.append((ln["de"], sent_dir / f"{sid}.mp3"))

    print(f"[info] {folder.name}: {len(word_tasks)} words, {len(sent_tasks)} lyric lines")

    sem = asyncio.Semaphore(8)

    async def run_one(text_str: str, dest: Path, label: str):
        async with sem:
            try:
                made = await synth(text_str, dest)
            except Exception as e:
                print(f"[err] {label} {dest.name}: {e}", file=sys.stderr)
                return
            print(f"[{'+' if made else '.'}] {label}: {dest.name}")

    print("[info] word audio...")
    await asyncio.gather(*[run_one(t, d, "word") for t, d in word_tasks])
    print("[info] sentence audio...")
    await asyncio.gather(*[run_one(t, d, "sent") for t, d in sent_tasks])

    # Write index.json + JS wrapper
    word_map = {}
    for w, _ in word_tasks:
        word_map[w] = f"audio/words/{slug(w)}.mp3"
    index = {
        "voice": VOICE,
        "rate": RATE,
        "words": word_map,
        "sentences": sent_records,
    }
    (folder / "audio" / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # JS wrapper for browser
    (folder / "audio_index.js").write_text(
        "// AUTO-GENERATED by generate_tts.py — do not edit.\n"
        "// Regenerate by running: python generate_tts.py <folder>\n"
        "window.TTS_INDEX = " + json.dumps(index, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"[done] {folder.name}: words={len(list(words_dir.glob('*.mp3')))}, "
          f"sentences={len(list(sent_dir.glob('*.mp3')))}")


if __name__ == "__main__":
    asyncio.run(main())
