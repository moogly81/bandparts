# Install

Three ways: Docker to just run it, Nix for a pinned toolchain, or the tools by
hand.

## With Docker

The image carries every tool, so it behaves the same on macOS, Linux and
Windows. Charts are mounted at run time, never copied into the image.

```sh
docker run --rm -v "$PWD/data:/work/data" moogly81/bandparts
```

Mount `manifests/` too and they are found by name, with nothing to pass:

```sh
docker run --rm \
  -v "$PWD/data:/work/data" \
  -v "$PWD/manifests:/work/manifests:ro" \
  moogly81/bandparts
```

The same image is on GitHub's registry if Docker Hub rate-limits you:
`ghcr.io/moogly81/bandparts`. Tags are releases, so `latest` follows the newest
`v*` tag rather than every commit to main.

The container runs as an ordinary user, so the parts belong to you; if your
account is not uid 1000, add `--user "$(id -u):$(id -g)"`. To run a MusicXML
tool instead of the splitter, override the entry point:

```sh
docker run --rm -v "$PWD:/work" --entrypoint musicxml-check \
  moogly81/bandparts score.mxl
```

### Without Docker Desktop

Any OCI runtime works. **Colima** keeps the `docker` CLI, so nothing on this
page changes:

```sh
brew install colima docker && colima start --cpu 4 --memory 8
```

**Podman** is daemonless; substitute `podman` for `docker` and add
`--userns keep-id`, or files come back owned by a subuid:

```sh
brew install podman && podman machine init && podman machine start
```

OrbStack is faster than either, but paid for commercial use - as is Docker
Desktop beyond personal use and small companies.

## With Nix

Nix pins `qpdf`, `ocrmypdf`, `tesseract` and friends to this project without
touching the rest of your machine.

```sh
# once per machine
sh <(curl -L https://nixos.org/nix/install) --daemon
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
exec $SHELL

# then
git clone https://github.com/moogly81/bandparts.git && cd bandparts
nix develop          # first run downloads the tools, a few minutes
```

Inside that shell every dependency is on `PATH`, and `bin/bandparts` runs.
Type `exit` and your machine is exactly as before. To run a single command
without entering it: `nix develop --command bin/bandparts --dry-run`.

To enter the shell automatically on `cd`, use [direnv](https://direnv.net)
with the `.envrc` already here:

```sh
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc && exec zsh
direnv allow                                           # once, in the repo
```

That also puts `bin/` on your `PATH` inside the repo, so the command is plain
`bandparts`. `.envrc` falls back to whatever is on `PATH` when Nix is absent.

## By hand

```sh
brew install qpdf poppler ocrmypdf exiftool
pip install pyyaml          # only needed for manifests
```

## Which tools you end up with

Docker and Nix give the same ones: the image is built from this repository's
`flake.nix`, from the same definition as the dev shell, so the `ocrmypdf` in
the container is the one contributors test with.

Installing by hand is the exception, and it matters more than it sounds:
`ocrmypdf` and `tesseract` decide how well a photocopy is read, so the same
scan can yield different text, and a different voice guess, on different
versions. If a chart splits correctly for you and not for someone else,
compare versions before assuming a bug:

```sh
ocrmypdf --version && tesseract --version | head -1
```

Whichever path you took: **OCR is not reproducible**. The same scan run twice
gives slightly different text. Expect small differences; be suspicious only of
large ones.

## Building the image yourself

```sh
nix build .#dockerImage   # Linux: produces a script that streams the image
./result | docker load
```

On macOS that output does not exist, the image being a Linux artefact. Rather
than pushing to CI to find out whether a change works, build it in a
container:

```sh
scripts/build-image          # ~30 seconds once warm
scripts/build-image --run    # ... and then split whatever is in data/in
```

The script hands Nix only the files git tracks, so your charts are never
copied into the build, and keeps its Nix store in a named volume.
