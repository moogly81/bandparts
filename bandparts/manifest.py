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
season can be reprocessed from a bare command with no arguments at all::

    _defaults:
      collection: BBCF 2026-2027
      languages: eng+spa+fra
      clean: true
      rename:
        Bass Trombone: Trombone 4
"""

from __future__ import annotations

import dataclasses
import os
import sys

DEFAULTS_KEY = "_defaults"

# Where a book's manifest is looked for, in order. {book} is the name of the
# folder the charts are in, so 'bbcf-2026-2027' finds
# 'manifests/bbcf-2026-2027.yaml' with nothing to type.
SEARCH = (
    "manifests/{book}.yaml",
    "manifests/{book}.yml",
    "{folder}/bandparts.yaml",
    "{folder}/bandparts.yml",
)


def discover(book: str, folder: str) -> str:
    """Path of the manifest belonging to a book, or "" if it has none.

    Two places: ``manifests/`` beside where you are working, which is what
    keeps manifests in git while the charts stay out of it, and a
    ``bandparts.yaml`` sitting with the charts themselves, for a book that
    travels as one folder.

    Charts loose in the input folder have no book name to look up, so only the
    second place applies to them.
    """
    for pattern in SEARCH:
        if not book and "{book}" in pattern:
            continue
        # normalised because a bookless chart makes 'folder' the input folder
        # itself, and joining "" onto it leaves a trailing separator
        candidate = os.path.normpath(pattern.format(book=book, folder=folder))
        if os.path.isfile(candidate):
            return candidate
    return ""


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
