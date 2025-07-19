{
  description = "dml-pdfclassify with stable Python";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      ...
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      pythonVersion = "3.13"; # 👈 change this to test other versions
      selectPython =
        pkgs:
        {
          "3.11" = pkgs.python311;
          "3.12" = pkgs.python312;
          "3.13" = pkgs.python313;
        }
        .${pythonVersion};
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = selectPython pkgs;
          project = pyproject-nix.lib.project.loadPyproject { projectRoot = ./.; };
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        {
          default = python.pkgs.buildPythonPackage attrs;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = selectPython pkgs;
          project = pyproject-nix.lib.project.loadPyproject { projectRoot = ./.; };
          pythonEnv = python.withPackages (project.renderers.withPackages { inherit python; });
        in
        {
          default = pkgs.mkShell {
            packages = [
              pythonEnv
              pkgs.poetry
            ];
          };
        }
      );
    };
}
