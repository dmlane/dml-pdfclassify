{
  description = "Nix flake for dml-pdfclassify (Poetry CLI using Python 3.12)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs systems (
          system:
          f {
            pkgs = import nixpkgs { inherit system; };
            system = system;
          }
        );
    in
    {
      packages = forAllSystems (
        { pkgs, system }:
        let
          dmlpdfclassifyPkg =
            (pkgs.python312Packages.buildPythonPackage {
              pname = "dml-pdfclassify";
              version = "2025.7.1039";
              format = "pyproject";

              src = ./.;

              nativeBuildInputs = [ pkgs.poetry ];
              propagatedBuildInputs = with pkgs.python312Packages; [
                sentence-transformers
                pdfminer-six
                joblib
                numpy
                platformdirs
                pypdf
                poetry-core
              ];

              pythonImportsCheck = [ "pdfclassify.pdfclassify" ];

              meta = {
                description = "Set of command-line tools (dml-pdfclassify)";
                homepage = "https://github.com/dmlane/dml-pdfclassify";
                license = pkgs.lib.licenses.mit;
              };
            }).overrideAttrs
              (_: {
                outputs = [ "out" ];
                pythonOutputDistPhase = "echo 'Skipping dist phase'";
                installCheckPhase = "true";
              });
        in
        {
          default = dmlpdfclassifyPkg;
          dml-pdfclassify = dmlpdfclassifyPkg;
        }
      );

      devShells = forAllSystems (
        { pkgs, ... }:
        {
          default = pkgs.mkShell {
            buildInputs = [
              pkgs.poetry
              pkgs.python312
            ];
          };
        }
      );
    };
}
