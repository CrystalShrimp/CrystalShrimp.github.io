"""Build pipeline for a music folder: regenerate audio + JSON, then sync the
generated JS into index.html.

Usage:
    python build.py [folder]

`folder` defaults to the current directory and must contain:
    - word_cards.xlsx          (source for word cards + example audio)
    - lyric.md or lyrics.md   (source for sentence + per-word audio)

Pipeline:
    1. generate_card_audio.py  — TTS for word_cards.xlsx words and examples
    2. word_card_to_json.py    — writes word_cards.{json,js}
    3. generate_tts.py         — TTS for lyric.md lines, writes audio_index.js
    4. inline word_cards.js + audio_index.js into index.html

If index.html does not exist, it is generated from template.html (next to
this script) with {{TITLE}} taken from the lyric's H1 and {{TRACKS}} from
folder/*.mp3. Either way the page uses inline <script> blocks marked with
the AUTO-GENERATED comments emitted by the generators.

Existing audio files are skipped (incremental), so re-running after editing
word_cards.xlsx / lyric.md only synthesizes new entries.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_script(name: str, folder: Path) -> None:
    print(f"\n>>> {name} {folder}")
    subprocess.run([sys.executable, str(HERE / name), str(folder)], check=True)


def inline_js(html_path: Path, js_path: Path, marker: str) -> None:
    """Replace the body of the inline <script> block containing `marker` with
    the contents of js_path."""
    html = html_path.read_text(encoding="utf-8")
    idx = html.find(marker)
    if idx == -1:
        print(f"[warn] marker {marker!r} not found in {html_path.name}; skipped")
        return
    open_start = html.rfind("<script", 0, idx)
    open_end = html.find(">", open_start) + 1
    close_idx = html.find("</script>", idx)
    if open_start < 0 or close_idx < 0:
        print(f"[warn] script boundaries not found for {marker} in {html_path.name}")
        return
    js_body = js_path.read_text(encoding="utf-8").rstrip() + "\n"
    new_html = html[:open_end] + "\n" + js_body + html[close_idx:]
    html_path.write_text(new_html, encoding="utf-8")
    print(f"[ok] inlined {js_path.name} -> {html_path.name}")


def inline_lyrics(html_path: Path, lyric_path: Path) -> None:
    """Replace the body of the `const LYRICS_RAW = \\`...\\`;` template literal
    with the current contents of lyric_path."""
    html = html_path.read_text(encoding="utf-8")
    prefix = "const LYRICS_RAW = `"
    start = html.find(prefix)
    if start == -1:
        print(f"[warn] LYRICS_RAW block not found in {html_path.name}; skipped")
        return
    content_start = start + len(prefix)
    end = html.find("`;", content_start)
    if end == -1:
        print(f"[warn] LYRICS_RAW block end not found in {html_path.name}")
        return
    lyrics = lyric_path.read_text(encoding="utf-8")
    new_html = html[:content_start] + lyrics + html[end:]
    html_path.write_text(new_html, encoding="utf-8")
    print(f"[ok] inlined {lyric_path.name} -> {html_path.name} (LYRICS_RAW)")


def scan_tracks(folder: Path) -> tuple[list[Path], str]:
    """Return (tracks, options_html) for files matching N.mp3 (1, 2, 3, ...),
    sorted numerically. Track 1 is marked selected (the default)."""
    tracks = sorted(
        [p for p in folder.glob("*.mp3") if re.match(r"^\d+\.mp3$", p.name)],
        key=lambda p: int(p.stem),
    )
    options = "\n".join(
        f'        <option value="{t.name}"{" selected" if i == 0 else ""}>{t.stem}</option>'
        for i, t in enumerate(tracks)
    )
    return tracks, options


def inline_tracks(html_path: Path, folder: Path) -> None:
    """Update #trackSelect options to match folder/N.mp3 (1 = default).
    No-op if no N.mp3 files are present, so pages with non-numeric names
    keep their hand-written options."""
    tracks, options = scan_tracks(folder)
    if not tracks:
        print(f"[warn] no N.mp3 files in {folder}; trackSelect left unchanged")
        return
    html = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<select class="track-select" id="trackSelect"[^>]*>).*?(</select>)',
        re.DOTALL,
    )
    new_html, n = pattern.subn(
        lambda m: m.group(1) + "\n" + options + "\n      " + m.group(2),
        html, count=1,
    )
    if n == 0:
        print(f"[warn] trackSelect not found in {html_path.name}")
        return
    html_path.write_text(new_html, encoding="utf-8")
    print(f"[ok] updated trackSelect with {len(tracks)} track(s) in {html_path.name}")


def from_template(html_path: Path, lyric_path: Path, folder: Path) -> None:
    """Generate index.html from template.html, substituting {{TITLE}} (from the
    lyric H1) and {{TRACKS}} (from folder/*.mp3). Requires template.html next
    to this script."""
    template = HERE / "template.html"
    if not template.exists():
        print(f"[error] {template} not found; cannot generate {html_path.name}",
              file=sys.stderr)
        sys.exit(1)
    html = template.read_text(encoding="utf-8")

    title = "Music"
    for line in lyric_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    tracks, options = scan_tracks(folder)

    html = html.replace("{{TITLE}}", title).replace("{{TRACKS}}", options)
    html_path.write_text(html, encoding="utf-8")
    print(f"[ok] generated {html_path.name} from template "
          f"(title={title!r}, tracks={len(tracks)})")


def main() -> None:
    folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

    if not (folder / "word_cards.xlsx").exists():
        print(f"[error] {folder / 'word_cards.xlsx'} not found", file=sys.stderr)
        sys.exit(1)
    lyrics = folder / "lyric.md"
    if not lyrics.exists():
        lyrics = folder / "lyrics.md"
    if not lyrics.exists():
        print(f"[error] no lyric.md/lyrics.md in {folder}", file=sys.stderr)
        sys.exit(1)

    html = folder / "index.html"
    if not html.exists():
        from_template(html, lyrics, folder)

    run_script("generate_card_audio.py", folder)
    run_script("word_card_to_json.py", folder)
    run_script("generate_tts.py", folder)

    inline_tracks(html, folder)
    inline_js(html, folder / "word_cards.js", "word_card_to_json.py")
    inline_js(html, folder / "audio_index.js", "generate_tts.py")
    inline_lyrics(html, lyrics)

    print(f"\n[done] {folder.name} rebuilt")


if __name__ == "__main__":
    main()
