# MusicXML

Splitting and tagging gives you a PDF to read from a stand. Turning the
printed notes back into notation is a different job, done by a different
program ([Audiveris](https://github.com/Audiveris/audiveris)), and the result
always needs repair. It is therefore optional.

## First: install Audiveris, and give it legacy OCR data

```sh
curl -LO https://github.com/Audiveris/audiveris/releases/download/5.11.0/Audiveris-5.11.0-macosx-arm64.dmg
hdiutil attach Audiveris-5.11.0-macosx-arm64.dmg
cp -R /Volumes/Audiveris/Audiveris.app /Applications/   # where bandparts looks
hdiutil detach /Volumes/Audiveris
```

The macOS build ships no OCR data, so it reads no text at all - no title, no
part name, no rehearsal marks - while otherwise appearing to work. Pointing it
at Homebrew's tesseract is not enough either: Audiveris uses Tesseract's
*legacy* engine, and Homebrew ships LSTM-only models. Fetch the full ones:

```sh
mkdir -p ~/.local/share/tessdata-legacy && cd ~/.local/share/tessdata-legacy
for l in eng fra spa ita; do
  curl -sSLO "https://github.com/tesseract-ocr/tessdata/raw/main/$l.traineddata"
done
```

`bandparts` looks in both places by default. Elsewhere, or for another
install, set `AUDIVERIS` to the executable.

## Recognising parts as they are split

```sh
bin/bandparts --omr          # off by default
```

Each part gets a `.mxl` beside its PDF, with the header already corrected and
the number of bars needing repair reported:

```
    p1-2 -> 5-10-15 Hours - Trombone 1.pdf
        5-10-15 Hours - Trombone 1.mxl, 7 bar(s) need repair
```

Recognition costs about a minute per part, so `--skip-existing` is worth
having on a book of any size ([usage](usage.md)). A failure never stops the
run: the PDF is what gets read from a stand, and it is already written. The
`.omr` beside the score is the Audiveris project, which you reopen in its
editor to correct the recognition.

Or do it by hand, one part at a time:

```sh
Audiveris -batch -export -output out/ "data/out/Tune - Trombone 1.pdf"
bin/musicxml-header "out/Tune - Trombone 1.mxl" --from-pdf "data/out/Tune - Trombone 1.pdf"
bin/musicxml-check  "out/Tune - Trombone 1.mxl"
```

## Repairing the header

`musicxml-header` exists because recognition reads the words correctly but
guesses their roles from position and size, and on a big-band part it guesses
wrong: the part name becomes the title, the tune name becomes a composer, the
arranger's key note becomes the movement. An editor then shows `Trombone 1`
where the tune should be.

Since the PDF was already tagged by `bandparts`, the true answers are known.
The fix labels the text already on the page and **never moves it**: those
positions came from the scan, and they are what make the result resemble the
original engraving.

What this does not fix is the notes. On a two-page trombone part, recognition
lost every multi-bar rest count and left six bars that do not add up. Text
quality and note quality are separate problems, and only the first has an easy
answer.

## Checking a score

If a notation editor calls a file "corrupted" without saying where, this says
which bars are at fault:

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

It exits non-zero when something is wrong, so it can gate a batch. Both `.mxl`
archives and plain `.xml` are read.

Repairing those bars means deciding what the music actually is, so it is left
to a musician: open the `.omr` in Audiveris, or the `.mxl` in MuseScore.

## Measuring how good the recognition is

Most of this collection is not scanned paper. Finale wrote it, so every
notehead and articulation is a glyph from a music font at an exact position,
and `pdftotext` gives them back as characters. The original is therefore
machine-readable ground truth, and recognition can be scored against it with
nobody labelling anything:

```sh
bin/omr-quality data/out
```

```
part                                       noteheads      accent     marcato      tenuto
Come Fly With Me - Trombone 1             195/226      26/23       58/58       21/1
Moanin' - Jazzin - Trombone 3             177/132      27/15       26/13        2/0

24 of 30 part(s) scored against their engraving, the rest scanned
            engraved  recognised    kept   wrong
noteheads       4018        3993     99%     11%
tenuto           148          81     55%     61%
```

Read `wrong`, not `kept`. A part that drops thirty notes and a part that
invents thirty average out to a perfect score, and above they very nearly do:
noteheads look 99% right while 11% of them are in fact wrong. Recognition
invents as readily as it drops, so both count as mistakes.

Below the table it lists faults that need no ground truth at all: a part that
produced no MusicXML, a missing title, bars that do not fill, and the credit
clutter that makes a notation editor stack text on top of itself.

To use it as a loop, keep the numbers from before your change:

```sh
bin/omr-quality data/out --json > before.json
# change something: a rendering resolution, an Audiveris option, a patch
bin/omr-quality data/out --baseline before.json
```

```
against before.json:
  tenuto       120 ->    91 wrong  (better)
```

Two things are deliberately not scored. Rests, because one engraved
multi-measure rest becomes many rests in MusicXML, which scored 234% and meant
nothing. And staccato, because its glyph is a dot and so is an augmentation
dot: `. œ J œ` is a dotted rhythm, not an articulation, and counting them
together claimed 37 staccatos in a part whose engraving has none. Telling
those apart needs the dot's position, which extracted text does not carry.

Scanned charts have no glyphs to read, so they are reported as unscorable
rather than as scoring zero. The fault checks still apply to them.
