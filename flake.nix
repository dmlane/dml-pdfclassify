{
  description = "Nix flake for dml-pdfclassify with configurable Python and unstable overrides";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unstable,
      pyproject-nix,
      ...
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # Configuration block
      pythonVersion = "3.12";
      unstableOverrides = [ "pypdf" ];

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
          unstable = import nixpkgs-unstable { inherit system; };

          python = selectPython pkgs;

          # Pull dependencies from pyproject
          project = pyproject-nix.lib.project.loadPyproject {
            projectRoot = ./.;
          };

          baseDeps = project.renderers.withPackages { inherit python; };

          # Patch selected packages from unstable into the environment
          overriddenDeps =
            baseDeps
            ++ (map (
              name: unstable.pythonPackages.${name} or (throw "Unstable package '${name}' not found")
            ) unstableOverrides);

          pythonEnv = python.withPackages (_: overriddenDeps);

          attrs = project.renderers.buildPythonPackage { inherit python; };

        in
        {
          default = python.pkgs.buildPythonPackage attrs;
          dml-pdfclassify = python.pkgs.buildPythonPackage attrs;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          unstable = import nixpkgs-unstable { inherit system; };

          python = selectPython pkgs;

          project = pyproject-nix.lib.project.loadPyproject {
            projectRoot = ./.;
          };

          baseDeps = project.renderers.withPackages { inherit python; };

          overriddenDeps =
            baseDeps
            ++ (map (
              name: unstable.pythonPackages.${name} or (throw "Unstable package '${name}' not found")
            ) unstableOverrides);

          pythonEnv = python.withPackages (_: overriddenDeps);

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
