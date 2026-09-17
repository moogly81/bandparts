# bandparts

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

Either let Nix provide everything, or install the four tools by hand.

### With Nix (recommended, and fine if you have never used it)

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

## Layout

```
bandparts/      the package: voice detection, PDF tools, tagging, CLI
bin/bandparts   wrapper so you can run it from anywhere in the repo
manifests/      per-book overrides
inbox/          drop raw charts here        (git-ignored)
parts/          generated parts land here   (git-ignored)
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
  result in MuseScore.
