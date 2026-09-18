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

from bandparts import musicxml
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


def bars(*contents: str) -> ET.Element:
    """A one-part score whose measures hold whatever is passed in."""
    measures = "".join(
        f"<measure number='{i + 1}'>{c}</measure>" for i, c in enumerate(contents)
    )
    return ET.fromstring(
        "<score-partwise version='4.0'>"
        "<part-list><score-part id='P1'><part-name>Tbn</part-name></score-part>"
        f"</part-list><part id='P1'>{measures}</part></score-partwise>"
    )


WHOLE_REST = "<note><rest/><duration>4</duration><type>whole</type></note>"
HALF_RESTS = "<note><rest/><duration>2</duration></note>" * 2
PLAYED = "<note><pitch><step>B</step><octave>3</octave></pitch><duration>4</duration></note>"


class CollapsingRests(unittest.TestCase):
    """A six-bar rest is written as one bar with a 6 over it, not six bars.

    Both say the same thing, but a player counting bars on a stand reads the
    number, and the part is meant to look like the one it came from.
    """

    def counts(self, root) -> list[str]:
        return [m.text for m in root.findall(".//multiple-rest")]

    def test_a_run_of_empty_bars_becomes_one(self):
        root = bars(PLAYED, WHOLE_REST, WHOLE_REST, WHOLE_REST, PLAYED)
        self.assertEqual(musicxml.collapse_rests(root), 1)
        self.assertEqual(self.counts(root), ["3"])

    def test_a_bar_written_as_two_half_rests_is_still_empty(self):
        # recognition writes the same silence differently from part to part
        root = bars(PLAYED, WHOLE_REST, HALF_RESTS, PLAYED)
        musicxml.collapse_rests(root)
        self.assertEqual(self.counts(root), ["2"])

    def test_a_single_empty_bar_is_left_alone(self):
        root = bars(PLAYED, WHOLE_REST, PLAYED)
        self.assertEqual(musicxml.collapse_rests(root), 0)
        self.assertEqual(self.counts(root), [])

    def test_a_repeat_inside_a_run_stops_it(self):
        # collapsing across a repeat would hide the repeat
        root = bars(
            WHOLE_REST,
            "<barline location='right'><repeat direction='backward'/></barline>"
            + WHOLE_REST,
            WHOLE_REST,
        )
        musicxml.collapse_rests(root)
        self.assertEqual(self.counts(root), [])

    def test_a_direction_inside_a_run_stops_it(self):
        # a tempo change or dynamic in an empty bar still has to be read
        root = bars(
            WHOLE_REST,
            "<direction><direction-type><words>Solo</words></direction-type></direction>"
            + WHOLE_REST,
            WHOLE_REST,
        )
        musicxml.collapse_rests(root)
        self.assertEqual(self.counts(root), [])

    def test_a_key_change_inside_a_run_stops_it(self):
        root = bars(
            WHOLE_REST,
            "<attributes><key><fifths>-2</fifths></key></attributes>" + WHOLE_REST,
            WHOLE_REST,
        )
        musicxml.collapse_rests(root)
        self.assertEqual(self.counts(root), [])

    def test_bars_with_notes_are_never_collapsed(self):
        root = bars(WHOLE_REST, PLAYED, WHOLE_REST)
        self.assertEqual(musicxml.collapse_rests(root), 0)

    def test_two_runs_are_collapsed_separately(self):
        root = bars(WHOLE_REST, WHOLE_REST, PLAYED, WHOLE_REST, WHOLE_REST, WHOLE_REST)
        self.assertEqual(musicxml.collapse_rests(root), 2)
        self.assertEqual(self.counts(root), ["2", "3"])

    def test_collapsing_does_not_change_the_music(self):
        # the bars stay; only how they are displayed changes
        root = bars(PLAYED, WHOLE_REST, WHOLE_REST, PLAYED)
        before = len(root.findall(".//measure")), len(root.findall(".//note"))
        musicxml.collapse_rests(root)
        after = len(root.findall(".//measure")), len(root.findall(".//note"))
        self.assertEqual(before, after)
