"""Optional optical music recognition, via Audiveris.

Turning the printed notes back into notation is a different problem from
splitting and tagging, done by a different program, and it is not reliable:
expect to repair the result by hand. It is therefore off unless asked for.

Two things about Audiveris are worth knowing, because neither is obvious and
both produce silent, confusing failures:

- It uses Tesseract's *legacy* engine, so the LSTM-only language data that
  Homebrew and most distributions ship will not load. Without the legacy
  models it reads no text at all, which costs you the title, the part name
  and every rehearsal mark, while still appearing to work.
- It reads the words but guesses their roles from position and size, and on
  a band part it guesses wrong. `scoreheader` puts the real ones back.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

#: Where the macOS installer puts it, since it is not on PATH from there.
MAC_APP = Path("/Applications/Audiveris.app/Contents/MacOS/Audiveris")

#: Language data we point Audiveris at, if the caller has not chosen.
TESSDATA_CANDIDATES = (
    Path.home() / ".local/share/tessdata-legacy",
    Path("/usr/share/tesseract-ocr/5/tessdata"),
    Path("/usr/share/tessdata"),
)


class RecognitionError(RuntimeError):
    pass


def find_audiveris() -> str | None:
    """The Audiveris command, or None when it is not installed."""
    override = os.environ.get("AUDIVERIS")
    if override:
        return override if Path(override).exists() else None
    found = shutil.which("Audiveris") or shutil.which("audiveris")
    if found:
        return found
    return str(MAC_APP) if MAC_APP.exists() else None


def legacy_tessdata() -> Path | None:
    """A folder holding legacy-compatible language data, if we can find one."""
    prefix = os.environ.get("TESSDATA_PREFIX")
    if prefix and (Path(prefix) / "eng.traineddata").exists():
        return Path(prefix)
    for candidate in TESSDATA_CANDIDATES:
        if (candidate / "eng.traineddata").exists():
            return candidate
    return None


def recognise(pdf: str, output_folder: str, timeout: int = 1800) -> Path:
    """Run Audiveris over one part and return the MusicXML it wrote."""
    command = find_audiveris()
    if command is None:
        raise RecognitionError(
            "Audiveris not found. Install it, or set AUDIVERIS to its "
            "executable. See the README section on optical music recognition."
        )

    environment = dict(os.environ)
    tessdata = legacy_tessdata()
    if tessdata is not None:
        environment["TESSDATA_PREFIX"] = str(tessdata)

    os.makedirs(output_folder, exist_ok=True)
    result = subprocess.run(
        [command, "-batch", "-export", "-output", output_folder, pdf],
        capture_output=True,
        text=True,
        env=environment,
        timeout=timeout,
    )

    produced = Path(output_folder) / (Path(pdf).stem + ".mxl")
    if not produced.exists():
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RecognitionError(
            f"Audiveris produced no score for {Path(pdf).name}"
            + (f": {detail[-1]}" if detail else "")
        )

    # Audiveris leaves a timestamped log beside the score. The .omr project
    # file stays, since that is what you reopen to correct the recognition,
    # but the log is noise in a folder that ends up on a music stand.
    for log in Path(output_folder).glob(f"{Path(pdf).stem}-*.log"):
        log.unlink()

    if tessdata is None:
        raise RecognitionError(
            f"{produced.name} written, but no legacy tessdata was found, so "
            "no text was read: the title, part name and rehearsal marks will "
            "be missing. See the README section on optical music recognition."
        )
    return produced
