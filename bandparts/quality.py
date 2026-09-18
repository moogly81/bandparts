"""Measure how much of an engraved part survived optical music recognition.

Most of this collection is not scanned paper: it is Finale output, where
every notehead and articulation is a glyph from a music font at an exact
position. `pdftotext` hands those glyphs back as characters. So for those
charts the original is machine-readable ground truth, free, and recognition
can be scored against it without anyone labelling anything by hand.

That makes a loop possible: change something, rerun, see whether the numbers
moved. Without it, "the quality is poor" cannot be told from "the quality is
poor in a different way".

Two cautions about what is counted.

- Only noteheads and articulations are scored, because only they compare
  one-to-one. Rests do not: one engraved multi-measure rest becomes many
  rests in MusicXML, which scored 234% and meant nothing.
- A count can be too high as easily as too low. Recognition invents notes as
  well as dropping them, and a part that scores 108% is not 8% better than
  perfect: it is wrong twice over. Both directions are reported as faults.

Scanned charts have no glyphs to read, so they are reported as unscorable
rather than as scoring zero, and the structural checks still apply to them.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import musicxml

#: Finale's fonts put these characters where the notes go: quarter (and
#: shorter, which share the glyph and differ by beam), half, whole.
NOTEHEADS = "\u0153\u02d9w"  # œ ˙ w

#: Articulation glyphs, in the same encoding.
#:
#: Staccato is deliberately absent. Its glyph is a dot, and so is an
#: augmentation dot: "." followed by a notehead is Finale's dotted rhythm,
#: not an articulation. Telling them apart needs the dot's position relative
#: to the notehead and the staff, which extracted text does not carry, and a
#: measurement that cannot tell them apart is worse than no measurement.
#: Counting them together claimed 37 staccatos in a part whose engraving has
#: none.
ARTICULATIONS = {"-": "tenuto", ">": "accent", "^": "marcato"}

#: Counted as music when a token is made only of these, but not scored:
#: accidentals, flags, rests and dots disambiguate neighbouring tokens like
#: "b>", where the flat would otherwise make the token look like prose.
INCIDENTAL = "b#.\u266d\u266fJ\u2030\u00d3\u0152\u2211"  # b # . ♭ ♯ J ‰ Ó Œ ∑

ALPHABET = set(NOTEHEADS) | set(ARTICULATIONS) | set(INCIDENTAL)

#: Below this many noteheads, the PDF is a scan (or draws its music as paths)
#: and there is nothing to score against.
ENGRAVED_MINIMUM = 10

#: More page-level credits than this and a notation editor stacks them on top
#: of one another at the top of page one. Observed: 4 on a clean part, 48 on
#: the worst.
CREDIT_CLUTTER = 8


@dataclass
class Inventory:
    """How many of each symbol a part contains."""

    noteheads: int = 0
    articulations: Counter = field(default_factory=Counter)

    @property
    def total_articulations(self) -> int:
        return sum(self.articulations.values())


def count_glyphs(text: str) -> Inventory:
    """Count music glyphs in text extracted from an engraved PDF.

    Words are what separate music from prose here. A token made only of music
    characters is music; anything holding a letter or a digit is text, which
    keeps the hyphens in "5-10-15 Hours" from being read as three tenutos and
    the "b" in "bucket" from being read as a flat.
    """
    inventory = Inventory()
    for token in text.split():
        if not token or not all(character in ALPHABET for character in token):
            continue
        for character in token:
            if character in NOTEHEADS:
                inventory.noteheads += 1
            elif character in ARTICULATIONS:
                inventory.articulations[ARTICULATIONS[character]] += 1
    return inventory


def engraved(pdf: Path) -> Inventory | None:
    """What the PDF itself says it contains, or None if it is a scan."""
    try:
        text = subprocess.run(
            ["pdftotext", "-raw", str(pdf), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    inventory = count_glyphs(text)
    return inventory if inventory.noteheads >= ENGRAVED_MINIMUM else None


def recognised(root: ET.Element) -> Inventory:
    """What the MusicXML claims, counted the same way."""
    notes = root.findall(".//note")
    inventory = Inventory(
        noteheads=len([n for n in notes if n.find("rest") is None])
    )
    for name, tag in (
        ("tenuto", "tenuto"),
        ("accent", "accent"),
        ("marcato", "strong-accent"),
        ("staccato", "staccato"),
    ):
        found = len(root.findall(f".//{tag}"))
        if found:
            inventory.articulations[name] = found
    return inventory


@dataclass
class Fault:
    """One thing wrong with a part, in the order we would fix it."""

    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


@dataclass
class Part:
    """One part, scored."""

    name: str
    pdf: Path
    score: Path | None = None
    source: Inventory | None = None
    result: Inventory | None = None
    faults: list[Fault] = field(default_factory=list)

    @property
    def scorable(self) -> bool:
        return self.source is not None and self.result is not None

    def recall(self, symbol: str) -> tuple[int, int] | None:
        """(engraved, recognised) for one symbol, or None when unscorable."""
        if not self.scorable:
            return None
        if symbol == "noteheads":
            return self.source.noteheads, self.result.noteheads
        return (
            self.source.articulations.get(symbol, 0),
            self.result.articulations.get(symbol, 0),
        )


def _title(root: ET.Element) -> str:
    for path in ("work/work-title", "movement-title"):
        text = (root.findtext(path) or "").strip()
        if text:
            return text
    return ""


def examine(pdf: Path) -> Part:
    """Score one part against its own PDF, and check it for breakage."""
    part = Part(name=pdf.stem, pdf=pdf)

    # Multi-movement recognition writes stem.mvt1.mxl and so on, rather than
    # stem.mxl. Those count as the part's scores; not looking for them is how
    # they escape the header patch.
    beside = sorted(pdf.parent.glob(f"{pdf.stem}.mvt*.mxl"))
    single = pdf.with_suffix(".mxl")
    scores = [single] if single.exists() else beside

    part.source = engraved(pdf)

    if not scores:
        part.faults.append(Fault("no score", "recognition produced no MusicXML"))
        return part
    if len(scores) > 1 or (beside and not single.exists()):
        part.faults.append(
            Fault("split", f"{len(scores)} movements: {', '.join(s.name for s in scores)}")
        )

    part.score = scores[0]
    total = Inventory()
    for path in scores:
        try:
            root = musicxml.read_score(path)
        except Exception as error:  # a file we cannot read is itself a fault
            part.faults.append(Fault("unreadable", f"{path.name}: {error}"))
            return part

        piece = recognised(root)
        total.noteheads += piece.noteheads
        total.articulations.update(piece.articulations)

        if not _title(root):
            part.faults.append(Fault("no title", path.name))
        credits = len(root.findall("credit"))
        if credits > CREDIT_CLUTTER:
            part.faults.append(
                Fault("credit clutter", f"{credits} page-level credits in {path.name}")
            )
        bad = musicxml.check_durations(root)
        if bad:
            part.faults.append(
                Fault("bad bars", f"{len(bad)} measure(s) do not fill the bar")
            )
    part.result = total
    return part


def survey(folder: Path) -> list[Part]:
    """Score every part in a folder, recursively."""
    return [examine(pdf) for pdf in sorted(folder.rglob("*.pdf"))]
