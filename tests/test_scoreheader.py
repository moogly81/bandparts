"""Tests for repairing a recognised score's header.

The fixtures imitate what optical music recognition actually produces: text
in the right places with the wrong roles attached.
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from bandparts.scoreheader import Header, apply


def recognised() -> ET.Element:
    """A score as Audiveris exports one: credits placed, roles guessed badly."""
    return ET.fromstring(
        """<score-partwise version="4.0">
          <movement-title>Key of G</movement-title>
          <identification>
            <creator type="lyricist">Trombone 1</creator>
            <creator type="composer">Arranged by Eyal Vilner</creator>
            <creator type="composer">5-10-15 Hours</creator>
          </identification>
          <credit page="1"><credit-words default-x="479" default-y="1563" font-size="35">5-10-15 Hours</credit-words></credit>
          <credit page="1"><credit-words default-x="164" default-y="1542" font-size="16">Trombone 1</credit-words></credit>
          <credit page="1"><credit-words default-x="624" default-y="1522" font-size="18">Key of G</credit-words></credit>
          <credit page="1"><credit-words default-x="979" default-y="1502" font-size="12">Arranged by Eyal Vilner</credit-words></credit>
          <credit page="1"><credit-words default-x="186" default-y="789" font-size="14">37</credit-words></credit>
          <credit page="1"><credit-words default-x="612" default-y="139" font-size="7">Copyright © Vilner 2017</credit-words></credit>
          <part-list><score-part id="P1"><part-name>Voice</part-name></score-part></part-list>
          <part id="P1"><measure number="1"/></part>
        </score-partwise>"""
    )


HEADER = Header(
    title="5-10-15 Hours",
    part="Trombone 1",
    composer="Ruth Brown",
    arranger="Eyal Vilner",
)


class ApplyHeader(unittest.TestCase):
    def setUp(self):
        self.root = recognised()
        apply(self.root, HEADER)

    def test_title_replaces_the_guess(self):
        self.assertEqual(self.root.findtext("work/work-title"), "5-10-15 Hours")

    def test_stray_movement_title_is_removed(self):
        # "Key of G" is an engraver's note, not the movement.
        self.assertIsNone(self.root.find("movement-title"))

    def test_creators_are_corrected(self):
        creators = {c.get("type"): c.text for c in self.root.findall("identification/creator")}
        self.assertEqual(creators, {"composer": "Ruth Brown", "arranger": "Eyal Vilner"})

    def test_part_is_named(self):
        self.assertEqual(self.root.findtext(".//part-name"), "Trombone 1")
        self.assertEqual(self.root.findtext(".//part-abbreviation"), "Tbn. 1")

    def test_credits_keep_their_position(self):
        # The layout is what makes the result resemble the original page, so
        # labelling or correcting a credit must never move it. Text may
        # change; coordinates may not.
        before = {
            w.get("default-x"): w.get("default-y")
            for w in recognised().findall(".//credit-words")
        }
        for words in self.root.findall(".//credit-words"):
            self.assertEqual(before[words.get("default-x")], words.get("default-y"))

    def test_credits_are_labelled_by_role(self):
        labelled = {
            c.findtext("credit-type"): c.findtext("credit-words")
            for c in self.root.findall("credit")
            if c.find("credit-type") is not None
        }
        self.assertEqual(labelled.get("title"), "5-10-15 Hours")
        self.assertEqual(labelled.get("part name"), "Trombone 1")
        self.assertEqual(labelled.get("arranger"), "Arranged by Eyal Vilner")
        self.assertEqual(labelled.get("rights"), "Copyright © Vilner 2017")

    def test_bar_numbers_are_dropped(self):
        # A bar number read as page text prints on top of the staff it was
        # read from, and an editor numbers the bars itself.
        words = [c.findtext("credit-words") for c in self.root.findall("credit")]
        self.assertNotIn("37", words)

    def test_words_we_cannot_place_are_left_alone(self):
        # Rehearsal marks and directions are most of the text on a part.
        # Mislabelling one as a title would move it to the top of the page,
        # and dropping it would lose it.
        kept = [
            c for c in self.root.findall("credit")
            if c.findtext("credit-words") == "Key of G"
        ]
        self.assertEqual(len(kept), 1)
        self.assertIsNone(kept[0].findtext("credit-type"))

    def test_rights_are_recorded(self):
        self.assertEqual(
            self.root.findtext("identification/rights"), "Copyright © Vilner 2017"
        )


class ParsePdfTags(unittest.TestCase):
    def test_reads_title_and_arranger(self):
        header = Header.from_pdf_tags("5-10-15 Hours - Trombone 1", "Ruth Brown (arr. Eyal Vilner)")
        self.assertEqual(
            (header.title, header.part, header.composer, header.arranger),
            ("5-10-15 Hours", "Trombone 1", "Ruth Brown", "Eyal Vilner"),
        )

    def test_composer_only(self):
        header = Header.from_pdf_tags("In The Mood - Trombone 4", "Joe Garland")
        self.assertEqual((header.composer, header.arranger), ("Joe Garland", ""))

    def test_arranger_only(self):
        header = Header.from_pdf_tags("Zaehringen - Trombone 3", "arr. Someone")
        self.assertEqual((header.composer, header.arranger), ("", "Someone"))


if __name__ == "__main__":
    unittest.main()


class MisreadCredits(unittest.TestCase):
    """What a scan produces: the right words, spelled wrong.

    An editor prints the credit, not <work-title>, so a title corrected only
    in <work> still shows the misreading on the page. These come from a real
    part: "EN THE MOOD", "TROMBONE T", and a bar number promoted to page text.
    """

    def setUp(self):
        self.root = ET.fromstring(
            """<score-partwise version="4.0">
              <credit page="1"><credit-words default-x="500" default-y="1500">EN THE MOOD</credit-words></credit>
              <credit page="1"><credit-words default-x="100" default-y="1520">TROMBONE T</credit-words></credit>
              <credit page="1"><credit-words default-x="900" default-y="1480">By JOE GARLAND</credit-words></credit>
              <credit page="1"><credit-words default-x="200" default-y="700">55</credit-words></credit>
              <credit page="1"><credit-words default-x="300" default-y="700">,55</credit-words></credit>
              <credit page="1"><credit-words default-x="400" default-y="700">=</credit-words></credit>
              <credit page="1"><credit-words default-x="600" default-y="650">Vamp Till Vocal</credit-words></credit>
              <part-list><score-part id="P1"><part-name>Voice</part-name></score-part></part-list>
              <part id="P1"><measure number="1"/></part>
            </score-partwise>"""
        )
        self.header = Header(
            title="In The Mood", part="Trombone 1", composer="Joe Garland"
        )
        self.changed = apply(self.root, self.header)

    def words(self):
        return [c.findtext("credit-words") for c in self.root.findall("credit")]

    def test_a_misread_title_is_corrected_on_the_page(self):
        self.assertIn("In The Mood", self.words())
        self.assertNotIn("EN THE MOOD", self.words())

    def test_a_misread_part_name_is_corrected(self):
        self.assertIn("Trombone 1", self.words())

    def test_text_that_already_holds_the_name_is_left_as_engraved(self):
        # "By JOE GARLAND" is what the page says and it is not wrong, so
        # replacing it with "Joe Garland" would lose a word.
        self.assertIn("By JOE GARLAND", self.words())

    def test_bar_numbers_are_dropped(self):
        for noise in ("55", ",55", "="):
            self.assertNotIn(noise, self.words())
        self.assertEqual(self.changed["dropped"], 3)

    def test_directions_survive(self):
        # Losing "Vamp Till Vocal" would lose the arrangement.
        self.assertIn("Vamp Till Vocal", self.words())

    def test_unrelated_text_is_never_corrected_into_a_title(self):
        header = Header(title="In The Mood", part="Trombone 1")
        root = ET.fromstring(
            """<score-partwise version="4.0">
              <credit page="1"><credit-words>Medium Swing</credit-words></credit>
              <part-list><score-part id="P1"><part-name>V</part-name></score-part></part-list>
              <part id="P1"><measure number="1"/></part>
            </score-partwise>"""
        )
        apply(root, header)
        self.assertEqual(
            [c.findtext("credit-words") for c in root.findall("credit")],
            ["Medium Swing"],
        )
