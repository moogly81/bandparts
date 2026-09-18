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


class LengthOutliers(unittest.TestCase):
    """The voices of one arrangement play the same number of bars.

    That makes the majority a reference needing no ground truth, and it is
    the only reliable one: an earlier version compared each part against the
    bar numbers printed on its page, which flagged twenty parts of
    twenty-four, because some engravings number every bar and others number
    every system.
    """

    def parts(self, lengths: dict[str, int]) -> list[quality.Part]:
        made = []
        for name, measures in lengths.items():
            part = quality.Part(name=name, pdf=Path(f"{name}.pdf"))
            part.measures = measures
            made.append(part)
        quality.outliers(made)
        return made

    def flagged(self, parts) -> list[str]:
        return [p.name for p in parts if any(f.kind == "length" for f in p.faults)]

    def test_a_part_twice_its_siblings_is_flagged(self):
        parts = self.parts(
            {
                "In The Mood - Trombone 1": 79,
                "In The Mood - Trombone 2": 80,
                "In The Mood - Trombone 3": 80,
                "In The Mood - Trombone 4": 158,
            }
        )
        self.assertEqual(self.flagged(parts), ["In The Mood - Trombone 4"])

    def test_ordinary_variation_is_not_flagged(self):
        parts = self.parts(
            {
                "Moanin' - Trombone 1": 78,
                "Moanin' - Trombone 2": 80,
                "Moanin' - Trombone 3": 76,
                "Moanin' - Bass Trombone": 78,
            }
        )
        self.assertEqual(self.flagged(parts), [])

    def test_a_part_far_shorter_is_flagged_too(self):
        # recognition giving up half way is as wrong as reading twice
        parts = self.parts(
            {
                "Blues - Trombone 1": 68,
                "Blues - Trombone 2": 69,
                "Blues - Trombone 3": 69,
                "Blues - Bass Trombone": 20,
            }
        )
        self.assertEqual(self.flagged(parts), ["Blues - Bass Trombone"])

    def test_tunes_are_judged_separately(self):
        parts = self.parts(
            {
                "Short Tune - Trombone 1": 30,
                "Short Tune - Trombone 2": 30,
                "Short Tune - Trombone 3": 30,
                "Long Tune - Trombone 1": 120,
                "Long Tune - Trombone 2": 120,
                "Long Tune - Trombone 3": 120,
            }
        )
        self.assertEqual(self.flagged(parts), [])

    def test_too_few_voices_to_judge(self):
        # one part of a tune has no majority to disagree with
        parts = self.parts({"Solo Tune - Trombone 1": 300})
        self.assertEqual(self.flagged(parts), [])
