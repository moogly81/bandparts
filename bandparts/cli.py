"""Command line entry point: a folder of raw charts in, tagged parts out."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

from . import manifest as manifests
from . import musicxml, omr, pdftools, scoreheader, tagging, voices


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bandparts",
        description="Split big-band chart PDFs into one tagged file per voice.",
    )
    parser.add_argument("--in", dest="source", metavar="FOLDER", default="data/in",
                        help="folder holding the raw charts (default: data/in)")
    parser.add_argument("--out", dest="destination", metavar="FOLDER", default="data/out",
                        help="folder to write the split parts to (default: data/out)")
    parser.add_argument("-l", "--languages", default="", help="tesseract languages used when a scan needs OCR (default eng+spa+fra)")
    parser.add_argument("-r", "--rename", action="append", default=[], metavar="OLD=NEW",
                        help="rename a detected voice, e.g. -r 'Bass Trombone=Trombone 4' (repeatable)")
    parser.add_argument("--clean", action="store_true", help="deskew and despeckle scans before splitting them")
    parser.add_argument("--omr", action="store_true",
                        help="also run optical music recognition, writing a .mxl beside each "
                             "part (needs Audiveris; the notes will need repair, see the docs)")
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


def find_charts(source: str) -> list[str]:
    """Every PDF under the input folder, as paths relative to it.

    Sub-folders are kept: 'bbcf-2026-2027/03.Bones/In The Mood.pdf' produces
    its parts under 'parts/bbcf-2026-2027/03.Bones/', so each book a band
    hands you stays separate without any extra flag.
    """
    found = []
    for folder, _, filenames in os.walk(source):
        for filename in filenames:
            if filename.lower().endswith(".pdf") and not filename.startswith("."):
                found.append(os.path.relpath(os.path.join(folder, filename), source))
    return sorted(found)


def transcribe(part: str, title: str, voice: str, composer: str, arranger: str) -> str:
    """Recognise one written part, then correct the header of the result.

    Recognition is best-effort by nature, so a failure here is reported and
    the run carries on: the PDF part, which is what people actually read
    from, has already been written.
    """
    produced = omr.recognise(part, os.path.dirname(part))
    header = scoreheader.Header(
        title=title, part=voice, composer=composer, arranger=arranger
    )
    scoreheader.rewrite(produced, header)

    problems = musicxml.check_durations(musicxml.read_score(produced))
    suffix = f", {len(problems)} bar(s) need repair" if problems else ""
    return f"{os.path.basename(produced)}{suffix}"


def run(options: argparse.Namespace) -> int:
    absent = pdftools.missing_tools()
    if absent:
        sys.exit("missing required tool(s): " + ", ".join(absent))

    if options.omr and not options.dry_run:
        if omr.find_audiveris() is None:
            sys.exit(
                "--omr needs Audiveris. Install it, or set AUDIVERIS to "
                "its executable; see the README."
            )
        if omr.legacy_tessdata() is None:
            print(
                "    ! no legacy tessdata found: recognition will read no "
                "text, so titles and rehearsal marks will be missing. See the "
                "README section on optical music recognition.",
                file=sys.stderr,
            )

    if not os.path.isdir(options.source):
        sys.exit(f"no such folder: {options.source}/")

    charts = find_charts(options.source)
    if not charts:
        sys.exit(f"no PDF found in {options.source}/")

    # one manifest per book, found by name and read the first time the book
    # is met; a book without one is processed on detection alone
    books: dict[str, tuple[dict[str, manifests.Entry], manifests.Defaults]] = {}

    def settings_for(chart: str):
        book = tagging.collection_from_folder(chart, options.source)
        if book not in books:
            folder = os.path.join(options.source, os.path.dirname(chart).split(os.sep)[0])
            path = manifests.discover(book, folder)
            if path:
                print(f"{book}: using {path}")
            books[book] = manifests.load(path)
        return book, books[book]

    command_line_renames = dict(pair.split("=", 1) for pair in options.rename)
    written = 0

    with tempfile.TemporaryDirectory(prefix="bandparts-") as workdir:
        for chart in charts:
            # before the chart is announced, so that the line reporting which
            # manifest a book uses appears above the book, not inside it
            book, (overrides, defaults) = settings_for(chart)
            print(chart)
            source = os.path.join(options.source, chart)
            entry = overrides.get(os.path.basename(chart), manifests.Entry())
            title = entry.title or tagging.title_from_filename(chart)

            # command line flags win over the book-wide settings of the manifest
            collection = defaults.collection or book
            languages = options.languages or defaults.languages or "eng+spa+fra"
            clean = options.clean or defaults.clean
            renames = {**defaults.rename, **command_line_renames}

            destination_folder = os.path.join(options.destination, os.path.dirname(chart))
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

                if options.omr:
                    try:
                        print(f"        {transcribe(destination, title, voice, entry.composer, entry.arranger)}")
                    except (omr.RecognitionError, subprocess.TimeoutExpired) as error:
                        print(f"        ! {error}", file=sys.stderr)

    verb = "would write" if options.dry_run else "wrote"
    print(f"\n{len(charts)} chart(s) read, {verb} {written} part(s) in {options.destination}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_arguments(argv))


if __name__ == "__main__":
    raise SystemExit(main())
