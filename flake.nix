{
  description = "bandparts - split big-band chart PDFs into one tagged file per voice";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs:
        let
          # the languages our charts are printed in
          tesseract = pkgs.tesseract.override {
            enableLanguages = [ "eng" "spa" "fra" "ita" "deu" ];
          };

          python = pkgs.python3.withPackages (ps: [ ps.pyyaml ]);

          runtimeTools = [
            pkgs.qpdf          # page extraction
            pkgs.poppler-utils # pdfinfo / pdftotext
            pkgs.ocrmypdf      # OCR for scans
            pkgs.exiftool      # document properties
            pkgs.unpaper       # deskew / despeckle, used by --clean
            pkgs.ghostscript   # ocrmypdf dependency
            tesseract
            python
          ];
        in
        {
          default = pkgs.mkShell {
            packages = runtimeTools;

            shellHook = ''
              echo "bandparts dev shell - python $(python3 --version | cut -d' ' -f2)"
              echo "  run: python3 -m bandparts.cli --dry-run"
            '';
          };
        });

      packages = forAllSystems (pkgs: {
        default = pkgs.python3Packages.buildPythonApplication {
          pname = "bandparts";
          version = "0.1.0";
          format = "pyproject";
          src = ./.;

          nativeBuildInputs = [ pkgs.python3Packages.setuptools ];
          propagatedBuildInputs = [ pkgs.python3Packages.pyyaml ];

          # the CLI shells out to these, so they must be on PATH at runtime
          makeWrapperArgs = [
            "--prefix PATH : ${pkgs.lib.makeBinPath [
              pkgs.qpdf
              pkgs.poppler-utils
              pkgs.ocrmypdf
              pkgs.exiftool
            ]}"
          ];

          doCheck = false;

          meta = with pkgs.lib; {
            description = "Split big-band chart PDFs into one clean, tagged file per voice";
            license = licenses.mit;
            mainProgram = "bandparts";
          };
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
