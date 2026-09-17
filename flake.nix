{
  description = "bandparts - split big-band chart PDFs into one tagged file per voice";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # x86_64-darwin is absent because nixpkgs 26.11 dropped it: Intel Macs
      # have to use the container image or install the tools by hand.
      systems = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Everything the CLI shells out to, defined once so the dev shell, the
      # packaged application and the container image cannot drift apart.
      toolchain = pkgs:
        let
          # the languages our charts are printed in
          tesseract = pkgs.tesseract.override {
            enableLanguages = [ "eng" "spa" "fra" "ita" "deu" ];
          };
        in
        [
          pkgs.qpdf          # page extraction
          pkgs.poppler-utils # pdfinfo / pdftotext
          pkgs.ocrmypdf      # OCR for scans
          pkgs.exiftool      # document properties
          pkgs.unpaper       # deskew / despeckle, used by --clean
          pkgs.ghostscript   # ocrmypdf dependency
          pkgs.libxml2       # xmllint, for the MusicXML schema check
          tesseract
        ];

      application = pkgs: pkgs.python3Packages.buildPythonApplication {
        pname = "bandparts";
        version = "0.1.0";
        format = "pyproject";
        src = ./.;

        nativeBuildInputs = [ pkgs.python3Packages.setuptools ];
        propagatedBuildInputs = [ pkgs.python3Packages.pyyaml ];

        # the CLI shells out to these, so they must be on PATH at runtime
        makeWrapperArgs = [
          "--prefix PATH : ${pkgs.lib.makeBinPath (toolchain pkgs)}"
        ];

        doCheck = false;

        meta = with pkgs.lib; {
          description = "Split big-band chart PDFs into one clean, tagged file per voice";
          license = licenses.mit;
          mainProgram = "bandparts";
        };
      };
    in
    {
      devShells = forAllSystems (pkgs:
        let
          python = pkgs.python3.withPackages (ps: [ ps.pyyaml ]);
        in
        {
          default = pkgs.mkShell {
            packages = (toolchain pkgs) ++ [ python ];

            shellHook = ''
              echo "bandparts dev shell - python $(python3 --version | cut -d' ' -f2)"
              echo "  run: python3 -m bandparts.cli --dry-run"
            '';
          };
        });

      packages = forAllSystems (pkgs:
        {
          default = application pkgs;
        }
        # A container image is a Linux artefact. Building one on macOS would
        # need a Linux builder, so the output simply does not exist there.
        // nixpkgs.lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          dockerImage =
            let
              app = application pkgs;

              # Without /etc/passwd the numeric user has no name and some
              # tools refuse to run; this is the standard way to give a
              # container image one without a package manager.
              users = pkgs.dockerTools.fakeNss.override {
                extraPasswdLines = [ "player:x:1000:1000:player:/work:/bin/sh" ];
                extraGroupLines = [ "player:x:1000:" ];
              };
            in
            pkgs.dockerTools.streamLayeredImage {
              name = "bandparts";
              tag = "latest";

              contents = [ app users pkgs.busybox pkgs.cacert ] ++ toolchain pkgs;

              # ocrmypdf writes page images here, and the data folders are the
              # mount points; both must exist and be writable by the user.
              fakeRootCommands = ''
                mkdir -p tmp work/data/inbox work/data/parts
                chmod 1777 tmp
                chown -R 1000:1000 work
              '';
              enableFakechroot = true;

              config = {
                Entrypoint = [ "${app}/bin/bandparts" ];
                # No arguments: the defaults read /work/data/inbox and write
                # /work/data/parts, so one mount and no flags is a full run.
                Cmd = [ ];
                WorkingDir = "/work";
                User = "1000:1000";
                Env = [
                  "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                  "LANG=C.UTF-8"
                ];
                Labels = {
                  "org.opencontainers.image.title" = "bandparts";
                  "org.opencontainers.image.description" =
                    "Split big-band chart PDFs into one clean, tagged file per voice";
                  "org.opencontainers.image.source" = "https://github.com/moogly81/bandparts";
                  "org.opencontainers.image.licenses" = "MIT";
                };
              };
            };
        });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
