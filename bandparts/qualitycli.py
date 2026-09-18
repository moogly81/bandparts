"""Command line for the recognition quality harness. See quality.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import quality

SYMBOLS = ("noteheads", "accent", "marcato", "tenuto")


def _percentage(engraved: int, recognised: int) -> str:
    if engraved == 0:
        return "    -" if recognised == 0 else f" +{recognised}"
    return f"{100 * recognised / engraved:4.0f}%"


def _table(parts: list[quality.Part], show_all: bool) -> None:
    header = f"{'part':40s}" + "".join(f"{s[:9]:>12s}" for s in SYMBOLS)
    print(header)
    print("-" * len(header))
    for part in parts:
        if not part.scorable:
            if show_all:
                why = "no score" if part.score is None else "scanned, nothing to score against"
                print(f"{part.name[:40]:40s}  {why}")
            continue
        row = f"{part.name[:40]:40s}"
        for symbol in SYMBOLS:
            engraved, recognised = part.recall(symbol)
            row += f"{engraved:5d}/{recognised:<6d}"[:12].rjust(12)
        print(row)


def _totals(parts: list[quality.Part]) -> dict[str, dict[str, int]]:
    """Totals per symbol, including the error the totals themselves hide.

    A part that drops thirty notes and a part that invents thirty average out
    to a perfect score, so `wrong` counts each part's mistakes separately and
    never lets them cancel. It is the number to drive down.
    """
    totals: dict[str, dict[str, int]] = {}
    for symbol in SYMBOLS:
        engraved = recognised = wrong = 0
        for part in parts:
            pair = part.recall(symbol)
            if pair:
                engraved += pair[0]
                recognised += pair[1]
                wrong += abs(pair[0] - pair[1])
        totals[symbol] = {
            "engraved": engraved,
            "recognised": recognised,
            "wrong": wrong,
        }
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omr-quality",
        description=(
            "Score recognised MusicXML against the engraving it came from. "
            "Run it before and after a change to see which way the quality "
            "moved."
        ),
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default="data/out",
        help="folder of parts, each a .pdf beside its .mxl (default: data/out)",
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="list unscorable parts too"
    )
    parser.add_argument(
        "-j", "--json", action="store_true", help="machine-readable, for sweeps"
    )
    parser.add_argument(
        "--baseline", metavar="FILE", help="compare against an earlier --json run"
    )
    arguments = parser.parse_args(argv)

    folder = Path(arguments.folder)
    if not folder.is_dir():
        print(f"no such folder: {folder}", file=sys.stderr)
        return 2

    parts = quality.survey(folder)
    if not parts:
        print(f"no parts in {folder}", file=sys.stderr)
        return 2

    totals = _totals(parts)
    faults = [(p, f) for p in parts for f in p.faults]

    if arguments.json:
        print(
            json.dumps(
                {
                    "folder": str(folder),
                    "parts": len(parts),
                    "scored": len([p for p in parts if p.scorable]),
                    "totals": totals,
                    "faults": [
                        {"part": p.name, "kind": f.kind, "detail": f.detail}
                        for p, f in faults
                    ],
                },
                indent=2,
            )
        )
        return 0

    _table(parts, arguments.all)

    scored = len([p for p in parts if p.scorable])
    print(
        f"\n{scored} of {len(parts)} part(s) scored against their engraving"
        f"{', the rest scanned or unrecognised' if scored != len(parts) else ''}"
    )
    print(f"{'':10s}{'engraved':>10s}{'recognised':>12s}{'kept':>8s}{'wrong':>8s}")
    for symbol in SYMBOLS:
        engraved = totals[symbol]["engraved"]
        recognised = totals[symbol]["recognised"]
        wrong = totals[symbol]["wrong"]
        share = f"{100 * wrong / engraved:.0f}%" if engraved else "-"
        print(
            f"{symbol:10s}{engraved:10d}{recognised:12d}"
            f"{_percentage(engraved, recognised):>8s}{share:>8s}"
        )
    print(
        "\n`kept` lets one part's losses cancel another's inventions; "
        "`wrong` does not.\nDrive `wrong` down."
    )

    if arguments.baseline:
        previous = json.loads(Path(arguments.baseline).read_text())
        print("\nagainst " + arguments.baseline + ":")
        for symbol in SYMBOLS:
            was = previous["totals"].get(symbol, {}).get("wrong", 0)
            now = totals[symbol]["wrong"]
            if now != was:
                verdict = "better" if now < was else "worse"
                print(f"  {symbol:10s} {was:5d} -> {now:5d} wrong  ({verdict})")
        if all(
            totals[s]["wrong"] == previous["totals"].get(s, {}).get("wrong")
            for s in SYMBOLS
        ):
            print("  no change")

    if faults:
        print(f"\n{len(faults)} fault(s):")
        for part, fault in faults:
            print(f"  {part.name[:44]:44s} {fault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
