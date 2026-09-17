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
        # labelling a credit must never move it.
        before = recognised()
        positions_before = [
            (w.get("default-x"), w.get("default-y"), w.text)
            for w in before.findall(".//credit-words")
        ]
        positions_after = [
            (w.get("default-x"), w.get("default-y"), w.text)
            for w in self.root.findall(".//credit-words")
        ]
        self.assertEqual(positions_before, positions_after)

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

    def test_bar_numbers_are_left_alone(self):
        # Most text on a part is bar numbers and rehearsal marks; mislabelling
        # one as a title would put it at the top of the page in an editor.
        roles = [
            c.findtext("credit-type")
            for c in self.root.findall("credit")
            if c.findtext("credit-words") in {"37", "Key of G"}
        ]
        self.assertEqual(roles, [None, None])

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
