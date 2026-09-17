# bandparts

[![ci](https://github.com/moogly81/bandparts/actions/workflows/ci.yml/badge.svg)](https://github.com/moogly81/bandparts/actions/workflows/ci.yml)

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
4. **Tag the result** with `exiftool`: title, composer, arranger, part and
   collection, so the files sort and search properly on a tablet.

## Install

Three ways, in order of least trouble: Docker if you just want to run it, Nix
if you want a pinned toolchain, or install the tools by hand.

### With Docker (nothing to install but Docker)

The image carries every tool already, so this works the same on macOS, Linux
and Windows. Your charts stay on your machine; they are mounted, never copied
into the image.

```sh
docker run --rm \
  -v "$PWD/inbox:/work/inbox:ro" \
  -v "$PWD/parts:/work/parts" \
  -v "$PWD/manifests:/work/manifests:ro" \
  moogly81/bandparts -m manifests/bbcf-2026-2027.yaml
```

Without a manifest it is shorter:

```sh
docker run --rm -v "$PWD/inbox:/work/inbox:ro" -v "$PWD/parts:/work/parts" \
  moogly81/bandparts
```

The container runs as an ordinary user so the parts it writes belong to you.
If your host account is not uid 1000, add `--user "$(id -u):$(id -g)"`.

To run the MusicXML checks instead of the splitter, override the entry point:

```sh
docker run --rm -v "$PWD:/work" --entrypoint musicxml-check \
  moogly81/bandparts score.mxl
```

### With Nix (a pinned toolchain, and fine if you have never used it)

Nix is a package manager that builds an isolated toolchain per project, so
`qpdf`, `ocrmypdf`, `tesseract` and friends are pinned here and never touch the
rest of your machine.

```sh
# 1. install Nix (multi-user, macOS or Linux) - once per machine
sh <(curl -L https://nixos.org/nix/install) --daemon

# 2. enable flakes, the format this repo uses - once per machine
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf

# 3. enter the project shell (first run downloads the tools, a few minutes)
cd bandparts
nix develop
```

Inside that shell every dependency is on `PATH`. Type `exit` to leave it and
your machine is exactly as before - nothing was installed globally.

To get the shell **automatically** whenever you `cd` into the repo, use
[direnv](https://direnv.net) with the `.envrc` already in this repo:

```sh
brew install direnv                                    # or: nix profile install nixpkgs#direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc && exec zsh
direnv allow                                           # once, in the repo
```

`.envrc` falls back to the tools already on your `PATH` if Nix is absent, so it
is safe either way.

### Without Nix

```sh
brew install qpdf poppler ocrmypdf exiftool
pip install pyyaml          # only needed for manifests
```

## Use

```sh
# drop the raw charts in inbox/, then
bin/bandparts

# see the plan without writing anything
bin/bandparts --dry-run

# a full run with credits, a house naming rule and cleaned-up scans
bin/bandparts \
    --collection "BBCF 2026-2027" \
    --manifest manifests/bbcf-2026-2027.yaml \
    --rename "Bass Trombone=Trombone 4" \
    --clean
```

| Option | Purpose |
| --- | --- |
| `-m, --manifest` | YAML overrides for titles, credits and page ranges |
| `-c, --collection` | value written to the Creator tag and keywords |
| `-r, --rename` | rewrite a voice name, repeatable (`'Bass Trombone=Trombone 4'`) |
| `-l, --languages` | tesseract languages for OCR (default `eng+spa+fra`) |
| `--clean` | deskew and despeckle scans before splitting |
| `-n, --dry-run` | report only; scans are not OCR'd, so they report no parts |

## Adding a new book

The repo is meant to accumulate books over the years, one folder per batch.
`inbox/` is walked recursively and the structure is mirrored into `parts/`:

```
inbox/bbcf-2026-2027/03-bones/*.pdf   ->   parts/bbcf-2026-2027/03-bones/*.pdf
inbox/quintet-2027/*.pdf              ->   parts/quintet-2027/*.pdf
```

So, for a new pile of charts:

1. `mkdir inbox/<band>-<season>` and drop the PDFs in it.
2. `bin/bandparts --dry-run` and read the plan. Most engraved charts need
   nothing else.
3. For whatever came out wrong, copy `manifests/bbcf-2026-2027.yaml` to
   `manifests/<band>-<season>.yaml` and fix those charts there. The
   `_defaults` block at the top carries the settings of the whole book:

   ```yaml
   _defaults:
     collection: BBCF 2026-2027
     languages: eng+spa+fra
     rename:
       Bass Trombone: Trombone 4
   ```

4. `bin/bandparts -m manifests/<band>-<season>.yaml` - and that one command
   reproduces the book from scratch any time, which is the point of keeping
   the manifest in git.

Instruments already recognised: trombone (incl. bass), trumpet, alto/tenor/
baritone sax, clarinet, flute, guitar, piano, bass, drums, vocal - in English,
Spanish, French and Italian. Add to `FAMILIES` in `bandparts/voices.py` for
anything else.

## Manifests

Detection covers most engraved charts. Hand-written headers and creative
filenames need help, and that is what a manifest is for - see
[`manifests/bbcf-2026-2027.yaml`](manifests/bbcf-2026-2027.yaml):

```yaml
"Quizas Quizas Quizas-78 pgs-1 (arrastrado).pdf":
  title: Quizas Quizas Quizas
  composer: Osvaldo Farres
  arranger: Joe d'Etienne
  parts:                      # explicit ranges win over detection
    Trombone 1: 1-4
    Trombone 2: 5-8
```

Every field is optional: an entry may fix the credits only and still let the
page ranges be found automatically.

## Checking MusicXML

A separate tool for the other direction: if you run a part through optical
music recognition and your notation editor calls the result "corrupted", this
says which bars are at fault.

```sh
bin/musicxml-check "5-10-15 Hours - Trombone 1.mxl"
```

```
5-10-15 Hours - Trombone 1.mxl
  structure: valid
  durations: 6 measure(s) do not fill the bar
    part P1 measure 13: 0/8 ticks, empty
    part P1 measure 35: 26/24 ticks, overfull by 2
```

Two independent checks, because a file can pass one and fail the other:

- **structure** - the official MusicXML schema, via `xmllint`. Fetched once
  into `~/.cache/bandparts` and patched so its imports resolve offline.
- **durations** - every measure's notes must add up to its time signature.
  This is what editors mean by corrupt, and what the schema cannot see.

It exits non-zero when something is wrong, so it can gate a batch. Reading
`.mxl` archives and plain `.xml` both work.

## Layout

```
bandparts/      the package: voice detection, PDF tools, tagging, CLI
bin/bandparts   wrapper so you can run it from anywhere in the repo
bin/musicxml-check  the MusicXML schema and bar-length checks
manifests/      per-book overrides
tests/          unit tests, run with python -m unittest discover -s tests
inbox/          drop raw charts here        (git-ignored)
parts/          generated parts land here   (git-ignored)
Dockerfile      the published image
flake.nix       pinned toolchain (nix develop)
.envrc          direnv hook that enters that toolchain automatically
```

Scores are copyrighted, so `inbox/` and `parts/` keep their contents out of
git. Only the tooling is versioned.

## Known limits

- Scans of hand-written headers are recognised poorly; use a manifest.
- A part whose header never names the instrument cannot be detected.
- OMR (turning the notes into MusicXML) is out of scope - feed the generated
  parts to [Audiveris](https://github.com/Audiveris/audiveris) and open the
  result in MuseScore. Expect to repair it: on a two-page trombone part it
  lost every multi-bar rest count and left six unusable bars, which is why
  `musicxml-check` exists.
