{
  description = "Nix flake for dml-pdfclassify using pyproject.nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    pyproject-nix.url = "github:nix-community/pyproject.nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
    }:
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
          project = pyproject-nix.lib.project.loadPoetryPyproject {
            projectDir = ./.;
          };
        in
        {
          default = project;
          dml-pdfclassify = project;
        }
      );

      devShells = forAllSystems (
        { pkgs, system }:
        {
          default = pkgs.mkShell {
            inputsFrom = [ self.packages.${system}.default ];
            packages = with pkgs; [
              poetry
              python312
            ];
          };
        }
      );
    };
}
