"""Tests for the MusicXML duration check.

The fixtures are written by hand rather than copied from a real score, so
the expected answer is known and no copyrighted music enters the repo.
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from bandparts.musicxml import check_durations, read_score


def score(measures: str, divisions: int = 4, beats: int = 4) -> ET.Element:
    return ET.fromstring(
        f"""<score-partwise version="4.0">
          <part-list><score-part id="P1"><part-name>Trombone 1</part-name></score-part></part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>{divisions}</divisions>
                <key><fifths>0</fifths></key>
                <time><beats>{beats}</beats><beat-type>4</beat-type></time>
                <clef><sign>F</sign><line>4</line></clef>
              </attributes>
              {measures}
            </measure>
          </part>
        </score-partwise>"""
    )


def note(duration: int, chord: bool = False, grace: bool = False) -> str:
    return (
        "<note>"
        + ("<grace/>" if grace else "")
        + ("<chord/>" if chord else "")
        + "<pitch><step>G</step><octave>3</octave></pitch>"
        + ("" if grace else f"<duration>{duration}</duration>")
        + "<voice>1</voice>"
        + "</note>"
    )


class DurationCheck(unittest.TestCase):
    def test_full_bar_passes(self):
        self.assertEqual(check_durations(score(note(4) * 4)), [])

    def test_short_bar_is_reported(self):
        problems = check_durations(score(note(4) * 3))
        self.assertEqual(len(problems), 1)
        self.assertEqual((problems[0].got, problems[0].expected), (12, 16))
        self.assertIn("short by 4", str(problems[0]))

    def test_overfull_bar_is_reported(self):
        problems = check_durations(score(note(4) * 5))
        self.assertEqual((problems[0].got, problems[0].expected), (20, 16))
        self.assertIn("overfull by 4", str(problems[0]))

    def test_empty_bar_is_reported(self):
        problems = check_durations(score(""))
        self.assertEqual(problems[0].got, 0)
        self.assertIn("empty", str(problems[0]))

    def test_chord_notes_sound_together(self):
        # Three notes of a chord occupy one beat between them, not three.
        chord = note(4) + note(4, chord=True) + note(4, chord=True)
        self.assertEqual(check_durations(score(chord + note(4) * 3)), [])

    def test_grace_notes_carry_no_duration(self):
        self.assertEqual(check_durations(score(note(0, grace=True) + note(4) * 4)), [])

    def test_second_voice_shares_the_bar(self):
        # backup rewinds the cursor so a second voice can fill the same bar.
        two_voices = note(4) * 4 + "<backup><duration>16</duration></backup>" + note(4) * 4
        self.assertEqual(check_durations(score(two_voices)), [])

    def test_multi_measure_rest_is_not_judged(self):
        rest = (
            "<attributes><measure-style><multiple-rest>8</multiple-rest>"
            "</measure-style></attributes><note><rest/><duration>16</duration></note>"
        )
        self.assertEqual(check_durations(score(rest)), [])

    def test_time_signature_is_respected(self):
        self.assertEqual(check_durations(score(note(4) * 3, beats=3)), [])
        self.assertEqual(len(check_durations(score(note(4) * 4, beats=3))), 1)


class ReadScore(unittest.TestCase):
    def test_reads_zipped_mxl(self):
        with TemporaryDirectory() as tmp:
            plain = Path(tmp) / "part.xml"
            plain.write_bytes(ET.tostring(score(note(4) * 4)))
            packed = Path(tmp) / "part.mxl"
            with zipfile.ZipFile(packed, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container><rootfiles><rootfile full-path="part.xml"/>'
                    "</rootfiles></container>",
                )
                archive.write(plain, "part.xml")
            root = read_score(packed)
            self.assertEqual(root.findtext(".//part-name"), "Trombone 1")


if __name__ == "__main__":
    unittest.main()
