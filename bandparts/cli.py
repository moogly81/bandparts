"""Command line entry point: inbox of raw charts in, tagged parts out."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from . import manifest as manifests
from . import pdftools, tagging, voices


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bandparts",
        description="Split big-band chart PDFs into one tagged file per voice.",
    )
    parser.add_argument("inbox", nargs="?", default="inbox", help="folder holding the raw charts (default: inbox)")
    parser.add_argument("parts", nargs="?", default="parts", help="folder to write the split parts to (default: parts)")
    parser.add_argument("-m", "--manifest", help="YAML overrides for titles, credits and page ranges")
    parser.add_argument("-c", "--collection", default="", help="tag every part with a collection, e.g. 'BBCF 2026-2027'")
    parser.add_argument("-l", "--languages", default="", help="tesseract languages used when a scan needs OCR (default eng+spa+fra)")
    parser.add_argument("-r", "--rename", action="append", default=[], metavar="OLD=NEW",
                        help="rename a detected voice, e.g. -r 'Bass Trombone=Trombone 4' (repeatable)")
    parser.add_argument("--clean", action="store_true", help="deskew and despeckle scans before splitting them")
    parser.add_argument("-n", "--dry-run", action="store_true", help="report what would be produced, write nothing")
    return parser.parse_args(argv)


def plan(source: str, entry: manifests.Entry, languages: str, clean: bool, workdir: str, dry_run: bool):
    """Return (readable_pdf, [(voice, first, last), ...]) for one chart."""
    pages = pdftools.count_pages(source)
    readable = source

    if not pdftools.has_text_layer(source, pages):
        print(f"    scan detected, running OCR ({languages})")
        if not dry_run:
            readable = os.path.join(workdir, os.path.basename(source))
            try:
                pdftools.ocr(source, readable, languages, clean)
            except pdftools.ToolError as error:
                print(f"    ! {error}", file=sys.stderr)

    if entry.parts:
        return readable, entry.blocks()

    detected = [voices.detect(pdftools.text_of_page(readable, page)) for page in range(1, pages + 1)]
    return readable, voices.group(detected)


def find_charts(inbox: str) -> list[str]:
    """Every PDF under the inbox, as paths relative to it.

    Sub-folders are kept: 'bbcf-2026-2027/03.Bones/In The Mood.pdf' produces
    its parts under 'parts/bbcf-2026-2027/03.Bones/', so each book a band
    hands you stays separate without any extra flag.
    """
    found = []
    for folder, _, filenames in os.walk(inbox):
        for filename in filenames:
            if filename.lower().endswith(".pdf") and not filename.startswith("."):
                found.append(os.path.relpath(os.path.join(folder, filename), inbox))
    return sorted(found)


def run(options: argparse.Namespace) -> int:
    absent = pdftools.missing_tools()
    if absent:
        sys.exit("missing required tool(s): " + ", ".join(absent))

    if not os.path.isdir(options.inbox):
        sys.exit(f"no such folder: {options.inbox}/")

    charts = find_charts(options.inbox)
    if not charts:
        sys.exit(f"no PDF found in {options.inbox}/")

    overrides, defaults = manifests.load(options.manifest)

    # command line flags win over the book-wide settings of the manifest
    collection = options.collection or defaults.collection
    languages = options.languages or defaults.languages or "eng+spa+fra"
    clean = options.clean or defaults.clean
    renames = {**defaults.rename, **dict(pair.split("=", 1) for pair in options.rename)}

    written = 0

    with tempfile.TemporaryDirectory(prefix="bandparts-") as workdir:
        for chart in charts:
            print(chart)
            source = os.path.join(options.inbox, chart)
            entry = overrides.get(os.path.basename(chart), manifests.Entry())
            title = entry.title or tagging.title_from_filename(chart)

            destination_folder = os.path.join(options.parts, os.path.dirname(chart))
            os.makedirs(destination_folder, exist_ok=True)

            readable, blocks = plan(source, entry, languages, clean, workdir, options.dry_run)
            if not blocks:
                print(f"    ! no voice recognised - add '{os.path.basename(chart)}' to a manifest", file=sys.stderr)
                continue

            for voice, first, last in blocks:
                voice = renames.get(voice, voice)
                destination = os.path.join(destination_folder, f"{title} - {voice}.pdf")
                print(f"    p{first}-{last} -> {os.path.basename(destination)}")
                written += 1
                if options.dry_run:
                    continue
                pdftools.extract_pages(readable, first, last, destination)
                pdftools.tag(destination, tagging.fields(title, voice, entry.composer, entry.arranger, collection))

    verb = "would write" if options.dry_run else "wrote"
    print(f"\n{len(charts)} chart(s) read, {verb} {written} part(s) in {options.parts}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_arguments(argv))


if __name__ == "__main__":
    raise SystemExit(main())
