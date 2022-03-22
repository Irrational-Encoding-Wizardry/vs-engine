{
  description = "Application packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlay
        (final: prev: {
        })
      ];
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        };

        makeVapourSynthPackage = ps: 
          # VapourSynth is not added as a proper
          # python package in nixpkgs. This will change that.
          (ps.toPythonModule (pkgs.vapoursynth.override {
            python3 = ps.python;
          }));

        lib = python: pkgs.poetry2nix.mkPoetryEnv {
          inherit python;

          projectDir = ./.;
          overrides = pkgs.poetry2nix.overrides.withDefaults (self: super: {
            vapoursynth = makeVapourSynthPackage self;
          });
          extraPackages = (ps: [
            ps.ipython
          ]);
        };
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            python310.pkgs.poetry
            poetry2nix
            (lib python310)
          ];
        };
      }));
}
