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
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .musicxml import read_score, write_score


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


#: How alike two lines must be to count as the same one misread. "EN THE
#: MOOD" against "In The Mood" scores 0.89; unrelated lines score far lower.
LIKENESS = 0.8


def _alike(text: str, known: str) -> bool:
    """Is this the known line, read badly?"""
    if not known:
        return False
    return SequenceMatcher(None, _normalise(text), _normalise(known)).ratio() >= LIKENESS


#: Credits holding nothing but digits and punctuation: bar numbers that
#: recognition promoted to page text. They carry no information an editor
#: cannot regenerate, and they sit at the coordinates they were read from,
#: which is on top of the music.
NOISE = re.compile(r"^[\d\s,.;:'\u2019\-=_|/\\()]+$")


def _role_of(text: str, header: Header) -> str | None:
    """Which credit a line of recognised text is, or None to leave it alone.

    Page numbers, rehearsal marks and bar counts are the bulk of the text on
    a part and must keep their positions untouched, so anything unrecognised
    is left exactly as it was.

    Matching is by likeness rather than equality, because the text being
    matched came from OCR: an exact comparison fails on precisely the lines
    most worth correcting.
    """
    value = _normalise(text)
    if not value:
        return None
    if header.title and _alike(text, header.title):
        return "title"
    if header.part and _alike(text, header.part):
        return "part name"
    if header.arranger and (_normalise(header.arranger) in value or _alike(text, header.arranger)):
        return "arranger"
    if header.composer and (_normalise(header.composer) in value or _alike(text, header.composer)):
        return "composer"
    if re.search(r"copyright|©|\ball rights\b", text, re.I):
        return "rights"
    return None


#: How far apart, vertically, two credits can be and still be one stacked
#: block of text. A line of a part's header is about 25 tenths high.
STACKED = 120


def _merge_stacked(root: ET.Element) -> int:
    """Join the composer and arranger into one block of two lines.

    Engravers stack them at the top right, and the coordinates recognition
    reads are right. Editors ignore those coordinates and place both credits
    in the same corner slot, so the two print on top of one another: "By JOE
    GARLANDArranged by MICHAEL SWEENEY". One credit holding two lines is what
    the page shows, and every renderer agrees about it.
    """
    found = {}
    for credit in root.findall("credit"):
        role = credit.findtext("credit-type")
        if role in ("composer", "arranger") and credit.find("credit-words") is not None:
            found[role] = credit
    if len(found) != 2:
        return 0

    def height(credit: ET.Element) -> float:
        return float(credit.find("credit-words").get("default-y") or 0)

    upper, lower = sorted(found.values(), key=height, reverse=True)
    if abs(height(upper) - height(lower)) > STACKED:
        return 0
    if upper.get("page") != lower.get("page"):
        return 0

    upper_words = upper.find("credit-words")
    lower_words = lower.find("credit-words")
    upper_words.text = f"{upper_words.text}\n{lower_words.text}"
    root.remove(lower)
    return 1


def apply(root: ET.Element, header: Header) -> dict[str, int]:
    """Rewrite the header of a parsed score in place. Returns what changed."""
    changed = {
        "work": 0,
        "creators": 0,
        "parts": 0,
        "credits": 0,
        "corrected": 0,
        "dropped": 0,
        "merged": 0,
    }

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

    # Label the words already on the page, and correct the ones we know the
    # true reading of. Editors display the credit, not the work title, so a
    # title fixed only in <work> still prints "EN THE MOOD" on the page.
    # Positions are left alone: they came from the engraving and are what
    # make the result resemble the original.
    truth = {
        "title": header.title,
        "part name": header.part,
        "composer": header.composer,
        "arranger": header.arranger,
    }
    for credit in list(root.findall("credit")):
        words = credit.find("credit-words")
        if words is None or not (words.text or "").strip():
            continue
        role = _role_of(words.text, header)
        if role is None:
            # Bar numbers read as page text, dropped rather than left to
            # print on top of the staff they were read from.
            if NOISE.match(words.text.strip()) and credit.find("credit-type") is None:
                root.remove(credit)
                changed["dropped"] += 1
            continue
        existing = credit.find("credit-type")
        if existing is None:
            existing = ET.Element("credit-type")
            credit.insert(0, existing)
        if existing.text != role:
            existing.text = role
            changed["credits"] += 1
        correct = truth.get(role, "")
        # Only rewrite what was misread. "Arranged by Eyal Vilner" already
        # holds the name and is what the page says, so replacing it with
        # "Eyal Vilner" would lose a word the engraver put there; "EN THE
        # MOOD" holds nothing and has to go.
        if correct and _normalise(correct) not in _normalise(words.text):
            words.text = correct
            changed["corrected"] += 1
        if role == "rights" and not header.rights:
            header.rights = words.text.strip()

    changed["merged"] = _merge_stacked(root)
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
    write_score(path, root)
    return changed
