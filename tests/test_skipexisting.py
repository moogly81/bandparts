"""--skip-existing: continue a run instead of rebuilding the book."""

import os
import shutil
import tempfile
import time
import unittest

from bandparts import cli


class IsCurrent(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="bandparts-test-")
        self.chart = self.write("chart.pdf")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, name, age=0.0):
        path = os.path.join(self.root, name)
        with open(path, "wb") as handle:
            handle.write(b"%PDF-1.4\n")
        if age:
            when = time.time() - age
            os.utime(path, (when, when))
        return path

    def test_a_part_written_after_its_chart_is_current(self):
        part = self.write("part.pdf")
        self.assertTrue(cli.is_current(part, self.chart))

    def test_a_part_older_than_its_chart_is_not(self):
        # the chart was corrected after the part was made, so redo it
        part = self.write("part.pdf", age=60)
        self.assertFalse(cli.is_current(part, self.chart))

    def test_a_part_that_does_not_exist_is_not_current(self):
        self.assertFalse(cli.is_current(os.path.join(self.root, "nope.pdf"), self.chart))

    def test_a_missing_chart_is_not_an_error(self):
        part = self.write("part.pdf")
        self.assertFalse(cli.is_current(part, os.path.join(self.root, "gone.pdf")))


class Flag(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(cli.parse_arguments([]).skip_existing)

    def test_the_flag_turns_it_on(self):
        self.assertTrue(cli.parse_arguments(["--skip-existing"]).skip_existing)


if __name__ == "__main__":
    unittest.main()
