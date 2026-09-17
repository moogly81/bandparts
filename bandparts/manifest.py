"""Optional per-file overrides, for charts that detection gets wrong.

A manifest is YAML keyed by source filename::

    "Quizas Quizas Quizas-78 pgs-1 (arrastrado).pdf":
      title: Quizas Quizas Quizas
      composer: Osvaldo Farres
      arranger: Joe d'Etienne
      parts:                 # explicit page ranges beat auto-detection
        Trombone 1: 1-4
        Trombone 2: 5-8

Every key is optional: a manifest entry may carry credits only and still let
the page ranges be detected automatically.

A reserved ``_defaults`` key holds the settings of the book as a whole, so a
season can be reprocessed with a single ``--manifest`` flag and no other
argument::

    _defaults:
      collection: BBCF 2026-2027
      languages: eng+spa+fra
      clean: true
      rename:
        Bass Trombone: Trombone 4
"""

from __future__ import annotations

import dataclasses
import sys

DEFAULTS_KEY = "_defaults"


@dataclasses.dataclass
class Defaults:
    """Book-wide settings; command line flags take precedence over these."""

    collection: str = ""
    languages: str = ""
    clean: bool = False
    rename: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Entry:
    title: str | None = None
    composer: str = ""
    arranger: str = ""
    parts: dict[str, str] = dataclasses.field(default_factory=dict)

    def blocks(self) -> list[tuple[str, int, int]]:
        """Explicit ranges as (voice, first_page, last_page)."""
        parsed = []
        for voice, span in self.parts.items():
            first, _, last = str(span).partition("-")
            parsed.append((voice, int(first), int(last or first)))
        return parsed


def load(path: str | None) -> tuple[dict[str, Entry], Defaults]:
    if not path:
        return {}, Defaults()
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment dependent
        sys.exit("reading a manifest needs PyYAML: pip install pyyaml")

    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    section = raw.pop(DEFAULTS_KEY, None) or {}
    defaults = Defaults(
        collection=section.get("collection", ""),
        languages=section.get("languages", ""),
        clean=bool(section.get("clean", False)),
        rename=section.get("rename") or {},
    )

    entries = {
        filename: Entry(
            title=entry.get("title"),
            composer=entry.get("composer", ""),
            arranger=entry.get("arranger", ""),
            parts=entry.get("parts") or {},
        )
        for filename, entry in raw.items()
    }
    return entries, defaults
