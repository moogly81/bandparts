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
