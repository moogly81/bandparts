"""Which PDFs count as charts to process."""

import os
import shutil
import tempfile
import unittest

from bandparts import cli


class FindCharts(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="bandparts-test-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"%PDF-1.4\n")
        return path

    def test_pdfs_are_found_with_their_sub_folders(self):
        self.write("in", "bbcf-2026-2027", "03-bones", "tune.pdf")
        self.assertEqual(
            cli.find_charts(os.path.join(self.root, "in")),
            [os.path.join("bbcf-2026-2027", "03-bones", "tune.pdf")],
        )

    def test_hidden_and_non_pdf_files_are_ignored(self):
        self.write("in", "tune.pdf")
        self.write("in", ".hidden.pdf")
        self.write("in", "notes.txt")
        self.assertEqual(cli.find_charts(os.path.join(self.root, "in")), ["tune.pdf"])

    def test_the_output_folder_inside_the_input_one_is_skipped(self):
        # otherwise the next run reads this run's parts as charts
        source = os.path.join(self.root, "in")
        destination = os.path.join(source, "out")
        self.write("in", "tune.pdf")
        self.write("in", "out", "tune - Trombone 1.pdf")
        self.assertEqual(cli.find_charts(source, destination), ["tune.pdf"])

    def test_an_output_folder_elsewhere_changes_nothing(self):
        source = os.path.join(self.root, "in")
        self.write("in", "tune.pdf")
        self.assertEqual(
            cli.find_charts(source, os.path.join(self.root, "out")), ["tune.pdf"]
        )

    def test_a_folder_merely_named_out_is_still_read(self):
        # only the actual destination is skipped, not anything called 'out'
        source = os.path.join(self.root, "in")
        self.write("in", "out", "tune.pdf")
        self.assertEqual(
            cli.find_charts(source, os.path.join(self.root, "parts")),
            [os.path.join("out", "tune.pdf")],
        )


if __name__ == "__main__":
    unittest.main()
