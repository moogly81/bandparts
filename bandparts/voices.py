"""Recognising which instrument and part number a page belongs to.

Charts come from many publishers and in several languages, so detection is
based on the page header only: the body of a part is full of note glyphs that
extract as noise and produce false positives.
"""

from __future__ import annotations

import re
import unicodedata

ORDINALS = {
    "1": 1, "1st": 1, "i": 1, "one": 1, "uno": 1,
    "2": 2, "2nd": 2, "ii": 2, "two": 2, "dos": 2,
    "3": 3, "3rd": 3, "iii": 3, "three": 3, "tres": 3,
    "4": 4, "4th": 4, "iv": 4, "four": 4, "cuatro": 4,
    "5": 5, "5th": 5, "v": 5, "five": 5, "cinco": 5,
}

ORDINAL_PATTERN = "|".join(sorted(ORDINALS, key=len, reverse=True))

#: canonical voice name -> pattern matching it in EN / ES / FR / IT.
#: Order matters: the most specific instrument has to be tried first, so that
#: "Bass Trombone" is never swallowed by the plain "Trombone" rule.
FAMILIES: list[tuple[str, str]] = [
    ("Bass Trombone", r"(?:bass[\s\-]*trombone|trombone[\s\-]*bass|tromb[o]n[\s\-]*bajo|trombone[\s\-]*basse)"),
    ("Trombone", r"(?:trombone|tromb[o]n|tromb\.?|tbn|bone)"),
    ("Trumpet", r"(?:trumpet|trompeta|trompette|tromba|tpt)"),
    ("Alto Sax", r"(?:alto[\s\-]*sax\w*|sax\w*[\s\-]*alto)"),
    ("Tenor Sax", r"(?:tenor[\s\-]*sax\w*|sax\w*[\s\-]*tenor)"),
    ("Baritone Sax", r"(?:bari\w*[\s\-]*sax\w*|sax\w*[\s\-]*baritono)"),
    ("Clarinet", r"(?:clarinet\w*|clarinete)"),
    ("Flute", r"(?:flute|flauta|flauto)"),
    ("Guitar", r"(?:guitar|guitarra|guitare)"),
    ("Piano", r"(?:piano|keys|teclado)"),
    ("Bass", r"(?:(?:double|string|electric)?[\s\-]*bass\b|contrabajo|contrebasse|bajo\b)"),
    ("Drums", r"(?:drums?\b|bater[i]a|batterie|percussion)"),
    ("Vocal", r"(?:vocal|voice|voz\b|chant)"),
]

#: instruments that never carry a part number in a big-band book
UNNUMBERED = frozenset({"Bass Trombone", "Guitar", "Piano", "Bass", "Drums", "Vocal"})

#: how many lines of a page count as "the header"
HEADER_LINES = 8


def deaccent(text: str) -> str:
    """Strip diacritics so 'Trombón' and 'Trombon' match the same rule."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalise(text: str, lines: int = HEADER_LINES) -> str:
    kept = [line.strip() for line in text.splitlines() if line.strip()][:lines]
    return deaccent(" ".join(kept)).lower()


def detect(text: str, lines: int = HEADER_LINES) -> str | None:
    """Return the canonical voice named in a page header, or None."""
    header = normalise(text, lines)

    for canonical, instrument in FAMILIES:
        match = re.search(rf"{instrument}\s*\.?\s*({ORDINAL_PATTERN})?\b", header)
        if not match:
            continue
        if canonical in UNNUMBERED:
            return canonical
        number = ORDINALS.get(match.group(1) or "")
        return f"{canonical} {number}" if number else canonical
    return None


def group(voices: list[str | None]) -> list[tuple[str, int, int]]:
    """Turn a per-page voice list into (voice, first_page, last_page) blocks.

    Pages where nothing was detected extend the block above them: continuation
    pages often print the part name too small or too oddly to be read back.
    A bare family name ('Trombone') right after a numbered one of the same
    family ('Trombone 1') is such a page, where note glyphs swallowed the
    number - not the start of a new part.
    """
    blocks: list[tuple[str, int, int]] = []
    for page, voice in enumerate(voices, start=1):
        if voice and blocks and blocks[-1][0].startswith(f"{voice} "):
            voice = None  # continuation of the numbered part above
        if voice and (not blocks or voice != blocks[-1][0]):
            blocks.append((voice, page, page))
        elif blocks:
            name, first, _ = blocks[-1]
            blocks[-1] = (name, first, page)
    return blocks
