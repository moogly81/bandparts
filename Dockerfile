# bandparts - split big-band chart PDFs into one tagged file per voice.
#
# The work is done by command line tools rather than Python libraries, so the
# image is mostly those tools. Debian carries all of them, which keeps this
# far simpler than pinning them by hand.
FROM python:3.12-slim-bookworm

# ocrmypdf pulls in ghostscript and pngquant; the rest are used directly.
#   qpdf            split and merge PDF pages
#   poppler-utils   read page text to find the instrument name
#   tesseract       OCR, one package per language we expect on a chart
#   exiftool        write title, composer and keywords
#   unpaper         deskew and despeckle scans
#   libxml2-utils   xmllint, for the MusicXML schema check
RUN apt-get update && apt-get install --no-install-recommends -y \
        ocrmypdf \
        qpdf \
        poppler-utils \
        unpaper \
        libimage-exiftool-perl \
        libxml2-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fra \
        tesseract-ocr-spa \
        tesseract-ocr-ita \
        tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml README.md ./
COPY bandparts ./bandparts
RUN pip install --no-cache-dir .

# Charts are the user's own property and never belong in the image; they are
# mounted at run time. Running as a normal user keeps the files written to
# those mounts owned by whoever started the container, not by root.
RUN useradd --create-home --uid 1000 player
USER player
WORKDIR /work

LABEL org.opencontainers.image.title="bandparts" \
      org.opencontainers.image.description="Split big-band chart PDFs into one clean, tagged file per voice" \
      org.opencontainers.image.source="https://github.com/moogly81/bandparts" \
      org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["bandparts"]
CMD ["--help"]
