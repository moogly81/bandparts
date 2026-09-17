"""Thin wrappers around the external PDF tools (poppler, qpdf, ocrmypdf)."""

from __future__ import annotations

import re
import shutil
import subprocess

REQUIRED_TOOLS = ("pdfinfo", "pdftotext", "qpdf", "ocrmypdf", "exiftool")

#: a page needs more than this many characters to count as "has real text"
TEXT_THRESHOLD = 20


class ToolError(RuntimeError):
    pass


def missing_tools() -> list[str]:
    return [tool for tool in REQUIRED_TOOLS if not shutil.which(tool)]


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True)


def count_pages(pdf: str) -> int:
    result = _run(["pdfinfo", pdf])
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.M)
    if not match:
        raise ToolError(f"cannot read the page count of {pdf}: {result.stderr.strip()}")
    return int(match.group(1))


def text_of_page(pdf: str, page: int) -> str:
    return _run(["pdftotext", "-f", str(page), "-l", str(page), "-layout", pdf, "-"]).stdout


def has_text_layer(pdf: str, pages: int, sample: int = 4) -> bool:
    """True when a scan-free text layer is already embedded in the file."""
    checked = min(pages, sample)
    with_text = sum(
        1 for page in range(1, checked + 1)
        if len(text_of_page(pdf, page).strip()) > TEXT_THRESHOLD
    )
    return with_text >= max(1, checked // 2)


def ocr(source: str, destination: str, languages: str, clean: bool = False) -> None:
    """Rasterise-and-recognise a scan. Falls back to a plain copy on failure."""
    command = ["ocrmypdf", "-l", languages, "--force-ocr", "--quiet"]
    if clean:
        command += ["--deskew", "--clean-final"]
    result = _run(command + [source, destination])
    if result.returncode != 0:
        shutil.copy(source, destination)
        raise ToolError(f"ocrmypdf exited {result.returncode}: {result.stderr.strip()[:200]}")


def extract_pages(source: str, first: int, last: int, destination: str) -> None:
    # --warning-exit-0: many band charts are structurally sloppy but readable,
    # and qpdf reports that with exit code 3.
    result = _run(["qpdf", "--warning-exit-0", source, "--pages", source, f"{first}-{last}", "--", destination])
    if result.returncode != 0:
        raise ToolError(f"qpdf failed on {source} p{first}-{last}: {result.stderr.strip()}")


def tag(pdf: str, fields: dict[str, str]) -> None:
    """Write PDF document properties with exiftool."""
    arguments = [f"-{key}={value}" for key, value in fields.items() if value]
    if arguments:
        _run(["exiftool", "-overwrite_original", "-q", *arguments, pdf])
