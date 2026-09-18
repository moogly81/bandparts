# Usage

```sh
bin/bandparts                               # data/in -> data/out
bin/bandparts --dry-run                     # report the plan, write nothing
bin/bandparts --in ~/charts --out ~/parts   # anywhere; nothing need live here
```

| Option | Purpose |
| --- | --- |
| `--in`, `--out` | folders to read and write (default `data/in`, `data/out`) |
| `-n, --dry-run` | report only; scans are not OCR'd, so they report no parts |
| `--clean` | deskew and despeckle scans before splitting |
| `-l, --languages` | tesseract languages for OCR (default `eng+spa+fra`) |
| `-r, --rename` | rewrite a voice name, repeatable (`'Bass Trombone=Trombone 4'`) |
| `--omr` | also recognise the notes, writing a `.mxl` beside each part ([docs](musicxml.md)) |
| `--skip-existing` | keep parts newer than their chart, to continue an interrupted run |

## Which book a part belongs to

The input tree is mirrored into the output one:

```
data/in/bbcf-2026-2027/03-bones/*.pdf -> data/out/bbcf-2026-2027/03-bones/*.pdf
```

The book is not an option: it is the first folder *inside* the input folder,
so that part is tagged `bbcf-2026-2027`, sub-folders counting as sections of
the book rather than books of their own. The input folder itself names nothing
- it is wherever the charts happen to sit today - so a chart loose in it has
no collection at all.

The name is used as written. For `BBCF 2026-2027` on the tablet, say so once
in the manifest, which also gives a loose pile its collection:

```yaml
_defaults:
  collection: BBCF 2026-2027
```

## Running it again

A run rebuilds the book: every chart is read again and its parts overwritten,
which is what keeps the manifest the only record of how the book was produced.

`--skip-existing` keeps any part newer than its chart, reporting it as
`(kept)`. That is how you continue an hour of `--omr` that stopped halfway:

```sh
bin/bandparts --omr --skip-existing
```

Correct a chart and its parts are older than it again, so they are rebuilt.
The PDF and its `.mxl` are judged separately, so a run stopped during
recognition transcribes rather than splits everything a second time. Reading
the chart is never skipped, OCR included: which parts it yields is only known
once its pages have been read.

The output folder may sit inside the input one - it is skipped when looking
for charts, so a run never reads the parts an earlier run wrote.

## Adding a new book

1. `mkdir data/in/<band>-<season>` and drop the PDFs in it.
2. `bin/bandparts --dry-run` and read the plan. Most engraved charts need
   nothing else.
3. For whatever came out wrong, copy `manifests/bbcf-2026-2027.yaml` to
   `manifests/<band>-<season>.yaml` - named after the folder, which is how it
   gets found - and fix those charts there:

   ```yaml
   _defaults:
     collection: BBCF 2026-2027
     languages: eng+spa+fra
     rename:
       Bass Trombone: Trombone 4
   ```

4. `bin/bandparts` again. The same bare command reproduces the book any time,
   which is the point of keeping the manifest in git.

Instruments recognised: trombone (incl. bass), trumpet, alto/tenor/baritone
sax, clarinet, flute, guitar, piano, bass, drums, vocal - in English, Spanish,
French and Italian. Add to `FAMILIES` in `bandparts/voices.py` for anything
else.

## Manifests

Detection covers most engraved charts. Hand-written headers and creative
filenames need help, and that is what a manifest is for.

There is no flag for it. A manifest is found by the name of the book, so
charts in `bbcf-2026-2027/` use `manifests/bbcf-2026-2027.yaml`, and the run
says which file it read. A book that travels as one folder can instead carry a
`bandparts.yaml` beside its charts; if both exist, `manifests/` wins. Charts
loose in the input folder have no name to look up, so only the second applies
to them. A book with no manifest is processed on detection alone.

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
page ranges be found automatically. See
[`manifests/bbcf-2026-2027.yaml`](../manifests/bbcf-2026-2027.yaml).
