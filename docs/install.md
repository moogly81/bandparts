# Install

Three ways, in order of least trouble: Docker if you just want to run it, Nix
if you want a pinned toolchain, or install the tools by hand.

## With Docker

The image carries every tool already, so it behaves the same on macOS, Linux
and Windows. Charts are mounted at run time, never copied into the image.

```sh
docker run --rm -v "$PWD/data:/work/data" moogly81/bandparts
```

With a manifest, mount that too:

```sh
docker run --rm \
  -v "$PWD/data:/work/data" \
  -v "$PWD/manifests:/work/manifests:ro" \
  moogly81/bandparts -m manifests/bbcf-2026-2027.yaml
```

The container runs as an ordinary user, so the parts it writes belong to you.
If your host account is not uid 1000, add `--user "$(id -u):$(id -g)"`.

To run one of the MusicXML tools instead of the splitter, override the entry
point:

```sh
docker run --rm -v "$PWD:/work" --entrypoint musicxml-check \
  moogly81/bandparts score.mxl
```

### You do not need Docker Desktop

Any OCI runtime works, and the command above is unchanged under the two
common free replacements on macOS.

**Colima** keeps the `docker` CLI, so nothing else in this page changes:

```sh
brew install colima docker
colima start --cpu 4 --memory 8
```

**Podman** is daemonless and rootless; substitute `podman` for `docker`:

```sh
brew install podman
podman machine init && podman machine start
podman run --rm -v "$PWD/data:/work/data" docker.io/moogly81/bandparts
```

One wrinkle worth knowing: rootless Podman maps your user to root inside the
container, so files come back owned by a high-numbered subuid unless you add
`--userns keep-id`. Colima does not have this problem.

OrbStack is faster than either and pleasant to use, but it is paid software
for commercial use. Docker Desktop is likewise free only for personal use and
small companies.

## With Nix

Nix builds an isolated toolchain per project, so `qpdf`, `ocrmypdf`,
`tesseract` and friends are pinned here and never touch the rest of your
machine. Fine if you have never used it:

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

Inside that shell every dependency is on `PATH`. Type `exit` to leave, and
your machine is exactly as before: nothing was installed globally.

To enter it **automatically** when you `cd` into the repo, use
[direnv](https://direnv.net) with the `.envrc` already here:

```sh
brew install direnv                                    # or: nix profile install nixpkgs#direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc && exec zsh
direnv allow                                           # once, in the repo
```

`.envrc` falls back to whatever is on your `PATH` when Nix is absent, so it is
safe either way.

## By hand

```sh
brew install qpdf poppler ocrmypdf exiftool
pip install pyyaml          # only needed for manifests
```

## The three paths do not give you the same tools

Each path takes the tools from a different place, and those places ship
different versions. At the time of writing:

| tool | Docker (Debian bookworm) | Nix (nixpkgs-unstable) |
| --- | --- | --- |
| ocrmypdf | 14.0.1 | 17.11.0 |
| tesseract | 5.3.0 | 5.5.3 |
| qpdf | 11.3.0 | 12.3.2 |
| poppler | 22.12.0 | 26.06.0 |
| exiftool | 12.57 | 13.59 |

This is not cosmetic. `ocrmypdf` and `tesseract` decide how well a photocopy
is read, so the same scan can produce different text, and therefore a
different voice guess, depending on how you installed. If a chart splits
correctly for you and not for someone else, compare versions before assuming
a bug:

```sh
ocrmypdf --version && tesseract --version | head -1
```

Debian and nixpkgs package different snapshots of the world, so no version
number could be pinned to make them agree; only building the image from the
flake would.

Worth knowing either way: **OCR is not reproducible**. The same scan, the same
image, run twice, gives slightly different text. Expect small differences
between runs, and be suspicious only of large ones.
