"""Check MusicXML files for the two kinds of breakage that matter.

Optical music recognition produces files that are structurally fine but
musically wrong. Two independent checks catch that:

structure  the official MusicXML schema, via xmllint
durations  every measure's notes must add up to its time signature

Notation editors reject a file on the second count while calling it
"corrupted", without saying which bar is at fault. This says which bar.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

SCHEMA_FILES = ("musicxml.xsd", "xlink.xsd", "xml.xsd")
SCHEMA_BASE = "https://raw.githubusercontent.com/w3c/musicxml/v4.0/schema"


@dataclass
class BadMeasure:
    """A measure whose contents do not fill the bar."""

    part: str
    number: str
    got: int
    expected: int

    def __str__(self) -> str:
        if self.got == 0:
            fault = "empty"
        elif self.got > self.expected:
            fault = f"overfull by {self.got - self.expected}"
        else:
            fault = f"short by {self.expected - self.got}"
        return (
            f"part {self.part} measure {self.number}: "
            f"{self.got}/{self.expected} ticks, {fault}"
        )


def read_score(path: Path) -> ET.Element:
    """Parse a .xml or .musicxml file, or the score inside a zipped .mxl."""
    if path.suffix.lower() != ".mxl":
        return ET.parse(path).getroot()

    with zipfile.ZipFile(path) as archive:
        name = None
        try:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//rootfile")
            if rootfile is not None:
                name = rootfile.get("full-path")
        except KeyError:
            pass
        if name is None:
            candidates = [
                n
                for n in archive.namelist()
                if n.lower().endswith((".xml", ".musicxml"))
                and not n.startswith("META-INF/")
            ]
            if not candidates:
                raise ValueError(f"{path.name}: no score inside the archive")
            name = candidates[0]
        return ET.fromstring(archive.read(name))


def write_score(path: Path, root: ET.Element) -> None:
    """Write a score back, preserving the zip container of a .mxl."""
    payload = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    if path.suffix.lower() != ".mxl":
        path.write_bytes(payload)
        return

    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    score_name = None
    for item, _ in entries:
        if item.filename.startswith("META-INF/"):
            continue
        if item.filename.lower().endswith((".xml", ".musicxml")):
            score_name = item.filename
            break
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries:
            archive.writestr(item, payload if item.filename == score_name else data)


#: A rest standing in for this many bars or more is written as one, with the
#: count above it. Two is where engravers start, and where the page stops
#: matching the score if we do not.
REST_RUN = 2

#: Anything of these inside a run of empty bars means the bars are not
#: interchangeable, and collapsing them would hide it: a repeat, an ending, a
#: rehearsal mark, a dynamic, a tempo change.
NOT_EMPTY = ("barline", "direction", "harmony", "sound")


def _is_empty_bar(measure: ET.Element) -> bool:
    """A bar holding only rests, and nothing that must stay visible."""
    if any(measure.find(tag) is not None for tag in NOT_EMPTY):
        return False
    notes = measure.findall("note")
    # Every note a rest, however the bar was written: recognition reports a
    # silent bar as one whole rest on one part and as two half rests on the
    # next, and both are equally empty.
    if not notes or any(note.find("rest") is None for note in notes):
        return False
    attributes = measure.find("attributes")
    if attributes is not None and (
        attributes.find("key") is not None or attributes.find("time") is not None
    ):
        return False
    return True


def collapse_rests(root: ET.Element) -> int:
    """Write runs of empty bars as multi-bar rests, the way the page does.

    Recognition reports a six-bar rest as six empty bars. Both are the same
    music, but only one of them looks like the part it came from, and a
    player counting bars on a stand reads the number above the rest.

    Returns the number of runs collapsed.
    """
    collapsed = 0
    for part in root.findall("part"):
        measures = part.findall("measure")
        start = 0
        while start < len(measures):
            if not _is_empty_bar(measures[start]):
                start += 1
                continue
            end = start
            while end + 1 < len(measures) and _is_empty_bar(measures[end + 1]):
                end += 1
            length = end - start + 1
            if length >= REST_RUN:
                first = measures[start]
                attributes = first.find("attributes")
                if attributes is None:
                    attributes = ET.Element("attributes")
                    first.insert(0, attributes)
                style = attributes.find("measure-style")
                if style is None:
                    style = ET.SubElement(attributes, "measure-style")
                multiple = style.find("multiple-rest")
                if multiple is None:
                    multiple = ET.SubElement(style, "multiple-rest")
                multiple.text = str(length)
                collapsed += 1
            start = end + 1
    return collapsed


def check_durations(root: ET.Element) -> list[BadMeasure]:
    """Return every measure whose notes do not add up to its time signature.

    Positions are tracked the way a reader does: chord notes sound with the
    note they hang off rather than after it, grace notes are stolen time and
    carry no duration of their own, and backup/forward move the cursor so a
    second voice can be written in the same bar. A measure is judged by how
    far the cursor ever reached, which is the length of its longest voice.
    """
    problems: list[BadMeasure] = []
    divisions = 1
    beats, beat_type = 4, 4

    for part in root.findall("part"):
        part_id = part.get("id", "?")
        for measure in part.findall("measure"):
            attributes = measure.find("attributes")
            if attributes is not None:
                if attributes.findtext("divisions"):
                    divisions = int(attributes.findtext("divisions"))
                time = attributes.find("time")
                if time is not None and time.findtext("beats"):
                    beats = int(time.findtext("beats"))
                    beat_type = int(time.findtext("beat-type"))

            expected = Fraction(divisions * 4 * beats, beat_type)
            position = 0
            furthest = 0
            for element in measure:
                if element.tag == "note":
                    if element.find("chord") is not None:
                        continue
                    if element.find("grace") is not None:
                        continue
                    position += int(element.findtext("duration", "0") or 0)
                elif element.tag == "backup":
                    position -= int(element.findtext("duration", "0") or 0)
                elif element.tag == "forward":
                    position += int(element.findtext("duration", "0") or 0)
                furthest = max(furthest, position)

            # A multi-measure rest stands in for many bars at once, so its
            # single rest is not meant to fill the bar it is written in.
            if measure.find(".//multiple-rest") is not None:
                continue
            if furthest != expected:
                problems.append(
                    BadMeasure(part_id, measure.get("number", "?"), furthest, int(expected))
                )
    return problems


def check_schema(path: Path, schema: Path) -> list[str]:
    """Validate against the MusicXML schema. Returns xmllint's complaints."""
    if shutil.which("xmllint") is None:
        raise RuntimeError("xmllint not found; skip with --no-schema")
    result = subprocess.run(
        ["xmllint", "--noout", "--schema", str(schema), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []
    return [line for line in result.stderr.splitlines() if line.strip()]


def fetch_schema(directory: Path) -> Path:
    """Download the MusicXML schema, if it is not already here.

    The published musicxml.xsd imports its two companion schemas by absolute
    URL, so a plain download validates nothing without a network. Rewrite
    those imports to sit next to it on disk.
    """
    directory.mkdir(parents=True, exist_ok=True)
    main = directory / "musicxml.xsd"
    if main.exists():
        return main

    for name in SCHEMA_FILES:
        target = directory / name
        subprocess.run(
            ["curl", "-sSLf", "-o", str(target), f"{SCHEMA_BASE}/{name}"],
            check=True,
        )

    text = main.read_text(encoding="utf-8")
    for name in ("xml.xsd", "xlink.xsd"):
        text = text.replace(f"http://www.musicxml.org/xsd/{name}", name)
    main.write_text(text, encoding="utf-8")
    return main
