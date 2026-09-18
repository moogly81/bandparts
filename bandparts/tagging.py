"""Deriving a clean tune title and writing consistent document properties."""

from __future__ import annotations

import os
import os
import re

from . import voices

#: leftovers from score-sharing sites, engraver exports and manual renames
NOISE_PATTERNS = (
    r"\(arrastrado\)",
    r"\barranged by\b[^-]*",
    r"\barr\.?\s+by\b[^-]*",
    r"\bcomplete\b",
    r"\bparts?\b",
    r"\bbig band\b",
    r"\bbones\b",
    r"\bscore\b",
    r"-\s*key of\s+\w+",
    r"\d+\s*pgs?(?:-\d+)?",
    r"\(.*?version.*?\)",
)


def title_from_filename(filename: str) -> str:
    """Best-effort tune title from a messy filename.

    'Blues for Fribourg - Trombon 2.pdf'                -> 'Blues for Fribourg'
    'Saint Louis - Arranged by X - Parts (arrastrado)'  -> 'Saint Louis'
    """
    stem = os.path.splitext(os.path.basename(filename))[0]

    # a trailing segment that is itself a voice name is a part marker, not title
    head, separator, tail = stem.rpartition(" - ")
    if separator and voices.detect(tail, lines=1):
        stem = head

    for pattern in NOISE_PATTERNS:
        stem = re.sub(pattern, " ", stem, flags=re.I)

    stem = re.sub(r"[\s_]+", " ", stem).strip(" -_")
    stem = re.sub(r"\s+\d+$", "", stem)  # 'My Tune 2' from a duplicated download
    return stem or "Untitled"


def collection_from_folder(chart: str) -> str:
    """The book a chart belongs to, taken from the folder holding it.

    Charts arrive one folder per book, so the folder already carries the
    answer: 'bbcf-2026-2027/03-bones/tune.pdf' belongs to 'bbcf-2026-2027'.
    Sub-folders are sections within a book, not books, so only the first
    component counts.

    The input folder itself names nothing. It is wherever the charts happen to
    sit today - '~/Downloads/originals', a scratch folder, a mounted disk - and
    letting it name the book tags parts with whatever that folder was called.
    A chart sitting loose in it therefore has no book, and no Collection tag,
    until a manifest gives it one.

    The name is used verbatim. Guessing that 'bbcf' wants to be 'BBCF' would
    be wrong as often as right; a manifest sets the pretty form explicitly.
    """
    return os.path.dirname(chart).split(os.sep)[0]


def credit(composer: str, arranger: str) -> str:
    """Single Author string from the composer and arranger, either optional."""
    if composer and arranger and composer != arranger:
        return f"{composer} (arr. {arranger})"
    if composer:
        return composer
    return f"arr. {arranger}" if arranger else ""


def fields(title: str, voice: str, composer: str = "", arranger: str = "", collection: str = "") -> dict[str, str]:
    """The document properties every generated part gets."""
    keywords = [value for value in (collection, title, voice) if value]
    return {
        "Title": f"{title} - {voice}",
        "Author": credit(composer, arranger),
        "Subject": f"{voice} part",
        "Keywords": ", ".join(keywords),
        "Creator": collection,
    }
