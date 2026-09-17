"""The book a part belongs to comes from the folder, not from a flag."""

import os
import unittest

from bandparts import tagging


class CollectionFromFolder(unittest.TestCase):
    def test_book_folder_names_the_collection(self):
        self.assertEqual(
            tagging.collection_from_folder("bbcf-2026-2027/tune.pdf", "data/inbox"),
            "bbcf-2026-2027",
        )

    def test_sections_within_a_book_are_not_collections(self):
        # 03-bones is a section of the book, so the book still wins
        self.assertEqual(
            tagging.collection_from_folder("bbcf-2026-2027/03-bones/tune.pdf", "data/inbox"),
            "bbcf-2026-2027",
        )

    def test_a_chart_loose_in_the_inbox_takes_the_inbox_name(self):
        self.assertEqual(
            tagging.collection_from_folder("tune.pdf", "/home/me/charts/quintet-2027"),
            "quintet-2027",
        )

    def test_a_trailing_separator_does_not_produce_an_empty_name(self):
        self.assertEqual(
            tagging.collection_from_folder("tune.pdf", "/home/me/charts/quintet-2027/"),
            "quintet-2027",
        )

    def test_the_name_is_used_verbatim(self):
        # no guessing that 'bbcf' wants to be 'BBCF'; a manifest does that
        self.assertEqual(
            tagging.collection_from_folder("bbcf_2026/tune.pdf", "data/inbox"),
            "bbcf_2026",
        )


class CollectionReachesTheTags(unittest.TestCase):
    def test_collection_is_written_to_creator_and_keywords(self):
        fields = tagging.fields("In The Mood", "Trombone 1", collection="bbcf-2026-2027")
        self.assertEqual(fields["Creator"], "bbcf-2026-2027")
        self.assertIn("bbcf-2026-2027", fields["Keywords"])


if __name__ == "__main__":
    unittest.main()
