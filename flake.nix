{
  description = "Nix flake for dml-pdfclassify using pyproject.nix";

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
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python312;
          project = pyproject-nix.lib.project.loadPyproject {
            projectRoot = ./.;
          };
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        {
          default = python.pkgs.buildPythonPackage (
            attrs
            // {
              # Ensure only 'out' is generated, not '-dist'
              outputs = [ "out" ];
              meta.outputsToInstall = [ "out" ];
              dontUseWheel = true;
              disabledBuildHooks = [ "pypaBuildHook" ]; # <- key addition
            }
          );
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python312;
          project = pyproject-nix.lib.project.loadPyproject {
            projectRoot = ./.;
          };
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
