"""Command line entry point for the MusicXML checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .musicxml import check_durations, check_schema, fetch_schema, read_score

DEFAULT_SCHEMA_DIR = Path.home() / ".cache" / "bandparts" / "musicxml-schema"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="musicxml-check",
        description="Report the measures a notation editor will call corrupt.",
    )
    parser.add_argument("scores", nargs="+", type=Path, help=".xml, .musicxml or .mxl")
    parser.add_argument(
        "--no-schema",
        action="store_true",
        help="skip schema validation (no download, no xmllint)",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=DEFAULT_SCHEMA_DIR,
        help=f"where to keep the MusicXML schema (default: {DEFAULT_SCHEMA_DIR})",
    )
    args = parser.parse_args(argv)

    schema = None
    if not args.no_schema:
        try:
            schema = fetch_schema(args.schema_dir)
        except Exception as error:  # noqa: BLE001 - schema is a convenience
            print(f"schema unavailable ({error}); checking durations only", file=sys.stderr)

    failed = False
    for score in args.scores:
        print(f"{score.name}")
        if not score.exists():
            print("  missing")
            failed = True
            continue

        if schema is not None and score.suffix.lower() != ".mxl":
            complaints = check_schema(score, schema)
            if complaints:
                failed = True
                print("  structure: invalid")
                for line in complaints[:10]:
                    print(f"    {line}")
            else:
                print("  structure: valid")

        try:
            root = read_score(score)
        except Exception as error:  # noqa: BLE001 - report and move on
            print(f"  unreadable: {error}")
            failed = True
            continue

        problems = check_durations(root)
        if problems:
            failed = True
            print(f"  durations: {len(problems)} measure(s) do not fill the bar")
            for problem in problems:
                print(f"    {problem}")
        else:
            print("  durations: every measure fills its bar")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
