# Usage

```sh
# drop the raw charts in data/inbox/, then
bin/bandparts

# see the plan without writing anything
bin/bandparts --dry-run

# a full run with credits, a house naming rule and cleaned-up scans
bin/bandparts \
    --manifest manifests/bbcf-2026-2027.yaml \
    --rename "Bass Trombone=Trombone 4" \
    --clean
```

The book each part belongs to is not an option: it comes from the folder the
chart sits in. `data/inbox/bbcf-2026-2027/03-bones/tune.pdf` is tagged
`bbcf-2026-2027`, sub-folders counting as sections of that book rather than
books of their own. Point the tool straight at a book and the same holds:

```sh
bin/bandparts ~/Dropbox/bbcf-2026-2027 ~/Dropbox/parts   # tagged bbcf-2026-2027
```

The folder name is used as it is written. If you want `BBCF 2026-2027` on the
tablet rather than `bbcf-2026-2027`, say so once in the manifest and it wins:

```yaml
_defaults:
  collection: BBCF 2026-2027
```

Both folders are positional, so nothing has to live in the checkout:

```sh
bin/bandparts ~/Dropbox/bbcf/charts ~/Dropbox/bbcf/parts
```

| Option | Purpose |
| --- | --- |
| `-m, --manifest` | YAML overrides for titles, credits and page ranges |
| `-r, --rename` | rewrite a voice name, repeatable (`'Bass Trombone=Trombone 4'`) |
| `-l, --languages` | tesseract languages for OCR (default `eng+spa+fra`) |
| `--clean` | deskew and despeckle scans before splitting |
| `--musicxml` | also run optical music recognition ([docs](musicxml.md)) |
| `-n, --dry-run` | report only; scans are not OCR'd, so they report no parts |

## Adding a new book

The repo is meant to accumulate books over the years, one folder per batch.
`data/inbox/` is walked recursively and the structure is mirrored into
`data/parts/`:

```
data/inbox/bbcf-2026-2027/03-bones/*.pdf -> data/parts/bbcf-2026-2027/03-bones/*.pdf
data/inbox/quintet-2027/*.pdf            -> data/parts/quintet-2027/*.pdf
```

So, for a new pile of charts:

1. `mkdir data/inbox/<band>-<season>` and drop the PDFs in it.
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
