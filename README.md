# bandparts

[![ci](https://github.com/moogly81/bandparts/actions/workflows/ci.yml/badge.svg)](https://github.com/moogly81/bandparts/actions/workflows/ci.yml)
[![docker](https://img.shields.io/docker/v/moogly81/bandparts?label=docker&sort=semver)](https://hub.docker.com/r/moogly81/bandparts)

Turns a pile of big-band chart PDFs into one clean, consistently named and
tagged file per voice.

Band books arrive as a mix of engraver exports, photocopies and multi-part
bundles: `In-The-Mood (arrastrado).pdf` holding four trombone parts, or a scan
with no text in it at all. `bandparts` reads each chart, works out which pages
belong to which instrument, and writes them out as `Title - Voice.pdf`.

## What it does to a chart

1. **OCR when needed** - a file with no text layer goes through `ocrmypdf`
   first, optionally deskewed and despeckled (`--clean`).
2. **Detect the voice of every page** from the page header, in English,
   Spanish, French or Italian (`Trombón Bajo`, `2nd Trumpet`, `Sax Alto`...).
3. **Split on voice changes** with `qpdf`, keeping continuation pages attached
   to the part they belong to.
4. **Tag the result** with `exiftool`: title, composer, arranger, part, and
   the book it came from - taken from the folder holding the chart, not typed
   in - so the files sort and search properly on a tablet.

## Quick start

Nothing to install but Docker. Put your charts in `data/in/`, then:

```sh
docker run --rm -v "$PWD/data:/work/data" moogly81/bandparts
```

```
bbcf-2026-2027/03-bones/In-The-Mood (arrastrado).pdf
    scan detected, running OCR (eng+spa+fra)
    p1-2 -> In The Mood - Trombone 1.pdf
    p3-4 -> In The Mood - Trombone 2.pdf

1 chart(s) read, wrote 2 part(s) in data/out/
```

Your charts are mounted, never copied into the image, and the files written
belong to you rather than to root.

Prefer to run it directly? `nix develop` gives you the whole toolchain, or
install `qpdf`, `poppler`, `ocrmypdf` and `exiftool` yourself - see
**[docs/install.md](docs/install.md)**.

## Documentation

| | |
| --- | --- |
| **[Install](docs/install.md)** | Docker, Nix or by hand, alternatives to Docker Desktop, and why the three paths do not give identical tools |
| **[Usage](docs/usage.md)** | every option, adding a new book, and manifests for the charts that need help |
| **[MusicXML](docs/musicxml.md)** | optional optical music recognition, repairing the header it produces, checking a score an editor calls corrupt, and scoring the recognition against the engraving it came from |
| **[Contributing](CONTRIBUTING.md)** | how to report a chart that is not recognised, and what makes a good patch |
| **[AGENTS.md](AGENTS.md)** | the brief to hand an AI assistant working on this repo |

## Layout

```
bandparts/          the package: voice detection, PDF tools, tagging, CLI
bin/                run the tools without installing them
manifests/          per-book overrides, kept in git
tests/              python -m unittest discover -s tests
docs/               the pages listed above
data/in/            drop raw charts here       (git-ignored)
data/out/           generated parts land here  (git-ignored)
flake.nix, .envrc   pinned toolchain: dev shell, package and published image
scripts/            build the image locally, including on macOS
```

Scores are copyrighted, so everything you put under `data/` is kept out of git
and out of the Docker build context; the two folders themselves are tracked
empty, so a fresh clone has somewhere to put charts. Only the tooling is
versioned. They are defaults, not requirements: `--in` and `--out` take any
path, so nothing need live in the checkout.

## Known limits

- Scans of hand-written headers are recognised poorly; use a manifest.
- A part whose header never names the instrument cannot be detected.
- Turning the notes back into notation is only as good as Audiveris, which is
  to say: expect to repair the result. On a two-page trombone part it lost
  every multi-bar rest count and left six unusable bars. See
  [docs/musicxml.md](docs/musicxml.md).

## Licence

MIT - see [LICENSE](LICENSE).
