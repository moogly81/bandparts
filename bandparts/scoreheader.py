"""Give an optically recognised score the right title, credits and part name.

Optical music recognition reads the words on the page but has to guess what
each one is for, and it guesses from position and size alone. On a big-band
part that guessing goes wrong in a predictable way: the arranger's key note
becomes the movement title, the tune name becomes a composer, and the part
name becomes a lyricist. A notation editor then shows the part name where
the title belongs.

We already know the true answers, because the PDF those pages came from was
tagged with them. This puts them back, and labels each piece of text on the
page with the role it actually plays, without moving anything: the positions
came from the scan and are what make the result resemble the original.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .musicxml import read_score


@dataclass
class Header:
    """What a part is, as opposed to what recognition guessed."""

    title: str = ""
    part: str = ""
    composer: str = ""
    arranger: str = ""
    rights: str = ""

    @classmethod
    def from_pdf_tags(cls, title_tag: str, author_tag: str) -> "Header":
        """Read back what bandparts wrote: 'Tune - Voice', 'X (arr. Y)'."""
        title, _, part = title_tag.partition(" - ")
        match = re.match(r"^(.*?)\s*\(arr\.\s*(.*?)\)\s*$", author_tag or "")
        if match:
            composer, arranger = match.group(1), match.group(2)
        elif (author_tag or "").lower().startswith("arr."):
            composer, arranger = "", author_tag[4:].strip()
        else:
            composer, arranger = author_tag or "", ""
        return cls(title.strip(), part.strip(), composer.strip(), arranger.strip())


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _role_of(text: str, header: Header) -> str | None:
    """Which credit a line of recognised text is, or None to leave it alone.

    Page numbers, rehearsal marks and bar counts are the bulk of the text on
    a part and must keep their positions untouched, so anything unrecognised
    is left exactly as it was.
    """
    value = _normalise(text)
    if not value:
        return None
    if header.title and value == _normalise(header.title):
        return "title"
    if header.part and value == _normalise(header.part):
        return "part name"
    if header.arranger and _normalise(header.arranger) in value:
        return "arranger"
    if header.composer and _normalise(header.composer) in value:
        return "composer"
    if re.search(r"copyright|©|\ball rights\b", text, re.I):
        return "rights"
    return None


def apply(root: ET.Element, header: Header) -> dict[str, int]:
    """Rewrite the header of a parsed score in place. Returns what changed."""
    changed = {"work": 0, "creators": 0, "parts": 0, "credits": 0}

    work = root.find("work")
    if work is None:
        work = ET.Element("work")
        root.insert(0, work)
    title_element = work.find("work-title")
    if title_element is None:
        title_element = ET.SubElement(work, "work-title")
    if header.title and title_element.text != header.title:
        title_element.text = header.title
        changed["work"] += 1

    # Recognition tends to park a stray line here, where editors render it as
    # a subtitle under the title. The part name has its own credit already.
    movement = root.find("movement-title")
    if movement is not None:
        root.remove(movement)
        changed["work"] += 1

    identification = root.find("identification")
    if identification is None:
        identification = ET.Element("identification")
        root.insert(list(root).index(work) + 1, identification)
    for creator in identification.findall("creator"):
        identification.remove(creator)
        changed["creators"] += 1
    for index, (role, value) in enumerate(
        (("composer", header.composer), ("arranger", header.arranger))
    ):
        if value:
            creator = ET.Element("creator")
            creator.set("type", role)
            creator.text = value
            identification.insert(index, creator)
            changed["creators"] += 1

    if header.rights:
        rights = identification.find("rights")
        if rights is None:
            rights = ET.SubElement(identification, "rights")
        rights.text = header.rights

    if header.part:
        for score_part in root.findall(".//score-part"):
            name = score_part.find("part-name")
            if name is None:
                name = ET.SubElement(score_part, "part-name")
            if name.text != header.part:
                name.text = header.part
                changed["parts"] += 1
            abbreviation = score_part.find("part-abbreviation")
            if abbreviation is None:
                abbreviation = ET.Element("part-abbreviation")
                score_part.insert(list(score_part).index(name) + 1, abbreviation)
            abbreviation.text = _abbreviate(header.part)

    # Label the words already on the page rather than adding new ones, so the
    # layout stays as it was engraved and an editor still knows what is what.
    for credit in root.findall("credit"):
        words = credit.find("credit-words")
        if words is None or not (words.text or "").strip():
            continue
        role = _role_of(words.text, header)
        if role is None:
            continue
        existing = credit.find("credit-type")
        if existing is not None and existing.text == role:
            continue
        if existing is None:
            existing = ET.Element("credit-type")
            credit.insert(0, existing)
        existing.text = role
        changed["credits"] += 1
        if role == "rights" and not header.rights:
            header.rights = words.text.strip()

    return changed


def _abbreviate(part: str) -> str:
    for full, short in (
        ("Trombone", "Tbn."),
        ("Trumpet", "Tpt."),
        ("Clarinet", "Cl."),
        ("Flute", "Fl."),
        ("Guitar", "Gtr."),
        ("Piano", "Pno."),
    ):
        if part.startswith(full):
            return part.replace(full, short, 1)
    if "Sax" in part:
        return part.replace("Saxophone", "Sax.")
    return part


def rewrite(path: Path, header: Header) -> dict[str, int]:
    """Apply the header to a score file, preserving the .mxl container."""
    root = read_score(path)
    changed = apply(root, header)
    payload = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

    if path.suffix.lower() != ".mxl":
        path.write_bytes(payload)
        return changed

    with zipfile.ZipFile(path) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    score_name = None
    for item, data in entries:
        if item.filename.startswith("META-INF/"):
            continue
        if item.filename.lower().endswith((".xml", ".musicxml")):
            score_name = item.filename
            break
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in entries:
            archive.writestr(item, payload if item.filename == score_name else data)
    return changed
