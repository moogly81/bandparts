"""The harness measures recognition, so its own measuring has to be right.

These test the two ways it could lie: counting prose as music, and counting
augmentation dots as articulations. Both did, before they were caught.
"""

from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from bandparts import quality

SCORE = """<?xml version="1.0"?>
<score-partwise version="4.0">
  <work><work-title>{title}</work-title></work>
  {credits}
  <part-list><score-part id="P1"><part-name>Trombone</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>1</divisions><time><beats>4</beats>
      <beat-type>4</beat-type></time></attributes>
    {notes}
  </measure></part>
</score-partwise>
"""

NOTE = """<note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration>
  <type>quarter</type>{dot}{articulation}</note>"""


def note(articulation: str = "", dotted: bool = False) -> str:
    mark = (
        f"<notations><articulations><{articulation}/></articulations></notations>"
        if articulation
        else ""
    )
    return NOTE.format(dot="<dot/>" if dotted else "", articulation=mark)


def score(title: str = "Moanin'", notes: str = "", credits: int = 0) -> str:
    return SCORE.format(
        title=title,
        notes=notes,
        credits="".join(
            f"<credit page='1'><credit-words>word {i}</credit-words></credit>"
            for i in range(credits)
        ),
    )


def write_mxl(path: Path, xml: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            "<container><rootfiles><rootfile full-path='score.xml'/>"
            "</rootfiles></container>",
        )
        archive.writestr("score.xml", xml)


class CountingGlyphs(unittest.TestCase):
    def test_counts_noteheads_of_every_duration(self):
        # quarter and shorter share a glyph; half and whole have their own
        self.assertEqual(quality.count_glyphs("\u0153 \u0153 \u02d9 w").noteheads, 4)

    def test_prose_is_not_music(self):
        # the hyphens are a title, the b is a mute direction, not a flat
        found = quality.count_glyphs("5-10-15 Hours bucket Vamp Till Vocal")
        self.assertEqual(found.noteheads, 0)
        self.assertEqual(found.total_articulations, 0)

    def test_articulations_glued_to_an_accidental(self):
        # "b>" is one token: a flat and an accent on the same note
        found = quality.count_glyphs("\u0153 b> \u0153")
        self.assertEqual(found.articulations["accent"], 1)

    def test_dots_are_never_articulations(self):
        # ". œ J œ" is a dotted quarter and an eighth, not a staccato, and
        # ".." is the pair beside a repeat barline
        found = quality.count_glyphs(". \u0153 J \u0153 .. \u02d9")
        self.assertEqual(found.total_articulations, 0)

    def test_the_three_scored_articulations(self):
        found = quality.count_glyphs("\u0153 - \u0153 ^ \u0153 >")
        self.assertEqual(found.articulations["tenuto"], 1)
        self.assertEqual(found.articulations["marcato"], 1)
        self.assertEqual(found.articulations["accent"], 1)


class CountingTheRecognition(unittest.TestCase):
    def test_rests_are_not_noteheads(self):
        xml = score(notes=note() + "<note><rest/><duration>3</duration></note>")
        found = quality.recognised(ET.fromstring(xml))
        self.assertEqual(found.noteheads, 1)

    def test_marcato_is_a_strong_accent(self):
        found = quality.recognised(ET.fromstring(score(notes=note("strong-accent"))))
        self.assertEqual(found.articulations["marcato"], 1)

    def test_an_augmentation_dot_is_not_an_articulation(self):
        found = quality.recognised(ET.fromstring(score(notes=note(dotted=True))))
        self.assertEqual(found.total_articulations, 0)


class ExaminingAPart(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        # Not a real PDF: there is nothing to extract, so the part is
        # unscorable, which is what every fault below is about anyway.
        self.pdf = self.folder / "Moanin' - Trombone 1.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 not really")

    def kinds(self, part):
        return {fault.kind for fault in part.faults}

    def test_recognition_that_produced_nothing_is_a_fault(self):
        part = quality.examine(self.pdf)
        self.assertIn("no score", self.kinds(part))
        self.assertFalse(part.scorable)

    def test_a_scan_is_unscorable_rather_than_zero(self):
        write_mxl(self.pdf.with_suffix(".mxl"), score(notes=note()))
        part = quality.examine(self.pdf)
        self.assertIsNone(part.source)
        self.assertIsNone(part.recall("noteheads"))

    def test_a_missing_title_is_a_fault(self):
        write_mxl(self.pdf.with_suffix(".mxl"), score(title="", notes=note()))
        self.assertIn("no title", self.kinds(quality.examine(self.pdf)))

    def test_credit_clutter_is_a_fault(self):
        # what stacks text on top of itself at the top of page one
        write_mxl(self.pdf.with_suffix(".mxl"), score(notes=note(), credits=40))
        self.assertIn("credit clutter", self.kinds(quality.examine(self.pdf)))

    def test_a_few_credits_are_not(self):
        write_mxl(self.pdf.with_suffix(".mxl"), score(notes=note(), credits=3))
        self.assertNotIn("credit clutter", self.kinds(quality.examine(self.pdf)))

    def test_movements_are_found_and_both_are_checked(self):
        # multi-movement recognition writes stem.mvtN.mxl, never stem.mxl,
        # which is how these escaped the header patch and lost their titles
        for movement in (1, 2):
            write_mxl(
                self.folder / f"{self.pdf.stem}.mvt{movement}.mxl",
                score(title="", notes=note()),
            )
        part = quality.examine(self.pdf)
        self.assertIn("split", self.kinds(part))
        self.assertNotIn("no score", self.kinds(part))
        self.assertEqual(len([f for f in part.faults if f.kind == "no title"]), 2)

    def test_bars_that_do_not_fill_are_a_fault(self):
        write_mxl(self.pdf.with_suffix(".mxl"), score(notes=note()))
        self.assertIn("bad bars", self.kinds(quality.examine(self.pdf)))


if __name__ == "__main__":
    unittest.main()
