# Contributing

Bug reports and patches are welcome. This is a small tool that solves a real
problem for one band, so the bar for a change is simple: does it help someone
get a readable, correctly named part onto a music stand?

## Getting set up

```sh
nix develop                  # or: brew install qpdf poppler ocrmypdf exiftool
python -m unittest discover -s tests -v
```

If you would rather not install anything, the Docker image carries the full
toolchain; see [docs/install.md](docs/install.md).

## The one hard rule

Never commit sheet music. `inbox/` and `parts/` are git-ignored because they
hold copyrighted scores, and tests build their own PDFs rather than shipping
a real one. Check `git status` before you commit.

## What makes a good patch

- **A real chart behind it.** This project is a pile of special cases that
  turned out to be general. If you are adding an instrument name or a
  language, it is because a chart in your book was not recognised. Say so in
  the commit message.
- **A test.** `tests/` uses only the standard library and builds its fixtures
  in code. Copy the nearest existing test.
- **Comments that explain why.** The what is already in the code.
- **One change per pull request**, without unrelated reformatting.

## Reporting a chart that is not recognised

Do not attach the PDF. Instead, tell us:

```sh
bin/bandparts --dry-run        # what it planned to do
pdftotext -f 1 -l 1 chart.pdf - | head -5   # what the header looks like
```

The first few lines of text, with the expected instrument name, is usually
enough to write the pattern. If the header is an image, say so: that is a
different problem (OCR quality) with a different fix.

## Using an AI assistant

That is fine, and [AGENTS.md](AGENTS.md) exists to give it the context it
needs. Two expectations:

- **You have read and understood the diff.** Review comments are addressed
  to you, not to the tool, and "the model wrote it" is not an answer to
  "why?".
- **Claims are checked.** If the pull request says it handles baritone sax,
  a test should show it, because a plausible-looking regex that never matches
  is the most common failure here.

No special labelling is required. Well-tested code is welcome whatever helped
you write it; code nobody understands is not.
