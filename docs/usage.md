# Usage

```sh
# drop the raw charts in data/in/, then
bin/bandparts

# see the plan without writing anything
bin/bandparts --dry-run

# the same, cleaning up scans as it goes
bin/bandparts --clean
```

The book each part belongs to is not an option: it comes from the folder the
chart sits in. `data/in/bbcf-2026-2027/03-bones/tune.pdf` is tagged
`bbcf-2026-2027`, sub-folders counting as sections of that book rather than
books of their own. Point the tool straight at a book and the same holds:

```sh
bin/bandparts --in ~/Dropbox/bbcf-2026-2027 --out ~/Dropbox/parts  # tagged bbcf-2026-2027
```

The folder name is used as it is written. If you want `BBCF 2026-2027` on the
tablet rather than `bbcf-2026-2027`, say so once in the manifest and it wins:

```yaml
_defaults:
  collection: BBCF 2026-2027
```

Both folders default to `data/`, and both can be pointed anywhere, so nothing
has to live in the checkout:

```sh
bin/bandparts --in ~/Dropbox/bbcf/charts --out ~/Dropbox/bbcf/parts
```

| Option | Purpose |
| --- | --- |
| `-r, --rename` | rewrite a voice name, repeatable (`'Bass Trombone=Trombone 4'`) |
| `-l, --languages` | tesseract languages for OCR (default `eng+spa+fra`) |
| `--clean` | deskew and despeckle scans before splitting |
| `--in`, `--out` | the folders to read and write (default `data/in`, `data/out`) |
| `--omr` | also run optical music recognition, writing a `.mxl` beside each part ([docs](musicxml.md)) |
| `-n, --dry-run` | report only; scans are not OCR'd, so they report no parts |

## Adding a new book

The repo is meant to accumulate books over the years, one folder per batch.
`data/in/` is walked recursively and the structure is mirrored into
`data/out/`:

```
data/in/bbcf-2026-2027/03-bones/*.pdf -> data/out/bbcf-2026-2027/03-bones/*.pdf
data/in/quintet-2027/*.pdf            -> data/out/quintet-2027/*.pdf
```

So, for a new pile of charts:

1. `mkdir data/in/<band>-<season>` and drop the PDFs in it.
2. `bin/bandparts --dry-run` and read the plan. Most engraved charts need
   nothing else.
3. For whatever came out wrong, copy `manifests/bbcf-2026-2027.yaml` to
   `manifests/<band>-<season>.yaml` - named after the folder, which is how it
   gets found - and fix those charts there. The `_defaults` block at the top
   carries the settings of the whole book:

   ```yaml
   _defaults:
     collection: BBCF 2026-2027
     languages: eng+spa+fra
     rename:
       Bass Trombone: Trombone 4
   ```

4. `bin/bandparts` again. The same bare command reproduces the book from
   scratch any time, which is the point of keeping the manifest in git.

Instruments already recognised: trombone (incl. bass), trumpet, alto/tenor/
baritone sax, clarinet, flute, guitar, piano, bass, drums, vocal - in English,
Spanish, French and Italian. Add to `FAMILIES` in `bandparts/voices.py` for
anything else.

## Manifests

Detection covers most engraved charts. Hand-written headers and creative
filenames need help, and that is what a manifest is for.

There is no flag for it: a manifest is found by the name of the book, so
charts in `bbcf-2026-2027/` use `manifests/bbcf-2026-2027.yaml`, and the run
says which file it read. A book that travels as a single folder can instead
carry a `bandparts.yaml` beside its charts; if both exist, `manifests/` wins.
A book with no manifest is processed on detection alone.

See
[`manifests/bbcf-2026-2027.yaml`](../manifests/bbcf-2026-2027.yaml):

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
