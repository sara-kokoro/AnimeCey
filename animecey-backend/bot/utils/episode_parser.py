"""Extract episode numbers from file names.

Patterns tested (most specific first):
  S02E05.mkv          → 5
  EP05.mkv            → 5
  Episode_128.mp4     → 128
  ep.24.mkv           → 24
  - 12.mkv            → 12
  E15_Anime.mkv       → 15
  07_title.mkv        → 7
"""

from __future__ import annotations

import re
from typing import Optional

_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"S\d+E(\d+)", re.IGNORECASE), 1),
    (re.compile(r"EP\.?(\d+)", re.IGNORECASE), 1),
    (re.compile(r"Episode\s*(\d+)", re.IGNORECASE), 1),
    (re.compile(r"ep\.(\d+)", re.IGNORECASE), 1),
    (re.compile(r"-\s*(\d+)"), 1),
    (re.compile(r"E(\d+)", re.IGNORECASE), 1),
    (re.compile(r"(?:^|\D)(\d{1,4})(?:\D|$)"), 1),
]


def parse_episode_number(filename: str) -> Optional[int]:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    for pattern, group in _PATTERNS:
        m = pattern.search(stem)
        if m:
            try:
                return int(m.group(group))
            except (ValueError, IndexError):
                continue
    return None
