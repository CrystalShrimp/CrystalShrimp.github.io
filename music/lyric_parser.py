"""Shared lyric parsing utility for tools and build scripts."""

from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fa5]")
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
