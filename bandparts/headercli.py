"""Command line entry point for repairing a recognised score's header."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .scoreheader import Header, rewrite


def tags_of(pdf: Path) -> tuple[str, str]:
    """Read back the Title and Author bandparts wrote onto a part."""
    result = subprocess.run(
        ["exiftool", "-s3", "-Title", "-Author", str(pdf)],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    return (lines[0] if lines else "", lines[1] if len(lines) > 1 else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="musicxml-header",
        description="Put the real title, credits and part name back on a "
        "score produced by optical music recognition.",
    )
    parser.add_argument("score", type=Path, help=".xml, .musicxml or .mxl")
    parser.add_argument(
        "--from-pdf",
        type=Path,
        help="take the details from a part tagged by bandparts",
    )
    parser.add_argument("--title")
    parser.add_argument("--part", help="the voice, for example 'Trombone 1'")
    parser.add_argument("--composer")
    parser.add_argument("--arranger")
    args = parser.parse_args(argv)

    if args.from_pdf:
        header = Header.from_pdf_tags(*tags_of(args.from_pdf))
    else:
        header = Header()
    for field in ("title", "part", "composer", "arranger"):
        value = getattr(args, field)
        if value:
            setattr(header, field, value)

    if not any((header.title, header.part, header.composer, header.arranger)):
        parser.error("nothing to apply: pass --from-pdf or the fields directly")

    changed = rewrite(args.score, header)
    print(f"{args.score.name}")
    print(f"  title    : {header.title or '(unchanged)'}")
    print(f"  part     : {header.part or '(unchanged)'}")
    print(f"  composer : {header.composer or '(none)'}")
    print(f"  arranger : {header.arranger or '(none)'}")
    print(
        "  rewrote  : "
        f"{changed['work']} title field(s), {changed['creators']} creator(s), "
        f"{changed['parts']} part name(s), {changed['credits']} credit(s) labelled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
