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

          base = project.renderers.buildPythonPackage { inherit python; };

          mergedAttrs = base // {
            outputs = [ "out" ];
            meta.outputsToInstall = [ "out" ];
            dontUseWheel = true;
            disabledBuildHooks = (base.disabledBuildHooks or [ ]) ++ [ "pypaBuildHook" ];
          };
        in
        {
          default = python.pkgs.buildPythonPackage mergedAttrs;
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
