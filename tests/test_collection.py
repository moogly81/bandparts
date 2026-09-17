"""The book a part belongs to comes from the folder, not from a flag."""

import os
import unittest

from bandparts import tagging


class CollectionFromFolder(unittest.TestCase):
    def test_book_folder_names_the_collection(self):
        self.assertEqual(
            tagging.collection_from_folder("bbcf-2026-2027/tune.pdf", "data/in"),
            "bbcf-2026-2027",
        )

    def test_sections_within_a_book_are_not_collections(self):
        # 03-bones is a section of the book, so the book still wins
        self.assertEqual(
            tagging.collection_from_folder("bbcf-2026-2027/03-bones/tune.pdf", "data/in"),
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
            tagging.collection_from_folder("bbcf_2026/tune.pdf", "data/in"),
            "bbcf_2026",
        )


class CollectionReachesTheTags(unittest.TestCase):
    def test_collection_is_written_to_creator_and_keywords(self):
        fields = tagging.fields("In The Mood", "Trombone 1", collection="bbcf-2026-2027")
        self.assertEqual(fields["Creator"], "bbcf-2026-2027")
        self.assertIn("bbcf-2026-2027", fields["Keywords"])


if __name__ == "__main__":
    unittest.main()


class ManifestDiscovery(unittest.TestCase):
    """A book's manifest is found by name, not passed on the command line."""

    def setUp(self):
        import tempfile

        from bandparts import manifest as manifests

        self.manifests = manifests
        self.root = tempfile.mkdtemp(prefix="bandparts-test-")
        self.cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        import shutil

        os.chdir(self.cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("_defaults:\n  collection: BBCF 2026-2027\n")
        return path

    def test_a_book_finds_the_manifest_named_after_it(self):
        self.write("manifests/bbcf-2026-2027.yaml")
        self.assertEqual(
            self.manifests.discover("bbcf-2026-2027", "data/in/bbcf-2026-2027"),
            "manifests/bbcf-2026-2027.yaml",
        )

    def test_another_books_manifest_is_not_used(self):
        self.write("manifests/quintet-2027.yaml")
        self.assertEqual(
            self.manifests.discover("bbcf-2026-2027", "data/in/bbcf-2026-2027"), ""
        )

    def test_a_manifest_may_travel_with_the_charts(self):
        self.write("charts/bbcf-2026-2027/bandparts.yaml")
        self.assertEqual(
            self.manifests.discover("bbcf-2026-2027", "charts/bbcf-2026-2027"),
            "charts/bbcf-2026-2027/bandparts.yaml",
        )

    def test_the_manifests_folder_wins_over_the_one_beside_the_charts(self):
        self.write("manifests/bbcf-2026-2027.yaml")
        self.write("charts/bbcf-2026-2027/bandparts.yaml")
        self.assertEqual(
            self.manifests.discover("bbcf-2026-2027", "charts/bbcf-2026-2027"),
            "manifests/bbcf-2026-2027.yaml",
        )

    def test_yml_spelling_is_accepted(self):
        self.write("manifests/bbcf-2026-2027.yml")
        self.assertEqual(
            self.manifests.discover("bbcf-2026-2027", "data/in/bbcf-2026-2027"),
            "manifests/bbcf-2026-2027.yml",
        )

    def test_a_book_without_a_manifest_is_not_an_error(self):
        self.assertEqual(self.manifests.discover("bbcf-2026-2027", "data/in"), "")
        self.assertEqual(self.manifests.load(""), ({}, self.manifests.Defaults()))
