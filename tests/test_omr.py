"""Tests for the optional optical music recognition step.

Audiveris itself is not exercised here: it is a large external program that
most machines running these tests will not have. What is tested is the part
that decides whether it can be used at all, since getting that wrong is what
produces a score with no text in it.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bandparts import omr


class FindAudiveris(unittest.TestCase):
    def test_env_override_wins(self):
        with TemporaryDirectory() as tmp:
            fake = Path(tmp) / "Audiveris"
            fake.write_text("")
            with mock.patch.dict("os.environ", {"AUDIVERIS": str(fake)}):
                self.assertEqual(omr.find_audiveris(), str(fake))

    def test_env_override_that_does_not_exist_is_not_used(self):
        # Silently falling back would hide the user's typo and then fail
        # much later, in a batch, with a confusing message.
        with mock.patch.dict("os.environ", {"AUDIVERIS": "/nope/Audiveris"}):
            self.assertIsNone(omr.find_audiveris())

    def test_falls_back_to_path(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/" + n if n == "Audiveris" else None):
                self.assertEqual(omr.find_audiveris(), "/usr/bin/Audiveris")


class LegacyTessdata(unittest.TestCase):
    def test_prefix_must_actually_hold_language_data(self):
        # Audiveris needs the legacy models; a folder without eng.traineddata
        # loads nothing and recognition reads no text while still "working".
        with TemporaryDirectory() as empty:
            with mock.patch.dict("os.environ", {"TESSDATA_PREFIX": empty}):
                with mock.patch.object(omr, "TESSDATA_CANDIDATES", ()):
                    self.assertIsNone(omr.legacy_tessdata())

    def test_prefix_with_language_data_is_used(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "eng.traineddata").write_text("")
            with mock.patch.dict("os.environ", {"TESSDATA_PREFIX": tmp}):
                self.assertEqual(omr.legacy_tessdata(), Path(tmp))

    def test_candidate_folder_is_found(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "eng.traineddata").write_text("")
            with mock.patch.dict("os.environ", {}, clear=True):
                with mock.patch.object(omr, "TESSDATA_CANDIDATES", (Path(tmp),)):
                    self.assertEqual(omr.legacy_tessdata(), Path(tmp))


class Recognise(unittest.TestCase):
    def test_missing_audiveris_explains_itself(self):
        with mock.patch.object(omr, "find_audiveris", return_value=None):
            with self.assertRaises(omr.RecognitionError) as raised:
                omr.recognise("part.pdf", "out")
            self.assertIn("AUDIVERIS", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
