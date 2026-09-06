"""Sync music folder index.html from template.html with word cards, audio index, and lyrics."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def scan_tracks(folder: Path) -> tuple[list[Path], str]:
    tracks = sorted(
        [p for p in folder.glob("*.mp3") if re.match(r"^\d+\.mp3$", p.name)],
        key=lambda p: int(p.stem),
    )
    options = "\n".join(
        f'        <option value="{t.name}"{" selected" if i == 0 else ""}>{t.stem}</option>'
        for i, t in enumerate(tracks)
    )
    return tracks, options


def inline_js_content(page_html: str, js_text: str, marker: str) -> str:
    idx = page_html.find(marker)
    if idx == -1:
        raise ValueError(f"Marker {marker!r} not found")
    open_start = page_html.rfind("<script", 0, idx)
    open_end = page_html.find(">", open_start) + 1
    close_idx = page_html.find("</script>", idx)
    return page_html[:open_end] + "\n" + js_text.rstrip() + "\n" + page_html[close_idx:]


def sync_music_html(folder: Path, custom_tracks_html: str | None = None, custom_default_track: str | None = None) -> Path:
    template_path = HERE / "template.html"
    html_path = folder / "index.html"
    lyric_path = folder / "lyrics.md" if (folder / "lyrics.md").exists() else folder / "lyric.md"

    html = template_path.read_text(encoding="utf-8")

    # 1. Title
    title = folder.name
    for line in lyric_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # 2. Tracks
    if custom_tracks_html is not None:
        options = custom_tracks_html
        default_track = custom_default_track or ""
    else:
        tracks, options = scan_tracks(folder)
        default_track = tracks[0].stem if tracks else ""

    html = (html.replace("{{TITLE}}", title)
                .replace("{{DEFAULT_TRACK}}", default_track)
                .replace("{{TRACKS}}", options))

    # 3. Inline word_cards.js
    wc_js_path = folder / "word_cards.js"
    if wc_js_path.exists():
        html = inline_js_content(html, wc_js_path.read_text(encoding="utf-8"), "word_card_to_json.py")

    # 4. Inline audio_index.js
    audio_js_path = folder / "audio_index.js"
    if audio_js_path.exists():
        html = inline_js_content(html, audio_js_path.read_text(encoding="utf-8"), "generate_tts.py")

    # 5. Inline lyrics
    prefix = "const LYRICS_RAW = `"
    start = html.find(prefix)
    content_start = start + len(prefix)
    end = html.find("`;", content_start)
    lyrics_text = lyric_path.read_text(encoding="utf-8")
    html = html[:content_start] + lyrics_text + html[end:]

    html_path.write_text(html, encoding="utf-8")
    print(f"[ok] Synced {html_path.relative_to(HERE.parent)} ({len(html)} bytes)")
    return html_path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    music1_options = (
        '        <option value="Schmutzige Seele_5m_1.mp3" selected>5m_1</option>\n'
        '        <option value="Schmutzige Seele_5m_2.mp3">5m_2</option>\n'
        '        <option value="Schmutzige Seele_1min_1.mp3">1min_1</option>\n'
        '        <option value="Schmutzige Seele_1min_2.mp3">1min_2</option>'
    )
    if target in ("all", "music_1"):
        sync_music_html(HERE / "music_1", custom_tracks_html=music1_options, custom_default_track="5m_1")
    if target in ("all", "music_2"):
        sync_music_html(HERE / "music_2")
    if target in ("all", "music_3"):
        sync_music_html(HERE / "music_3")
    if target in ("all", "music_4"):
        sync_music_html(HERE / "music_4")
