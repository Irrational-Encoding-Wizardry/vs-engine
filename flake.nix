{
  description = "Application packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  # VS latest
  inputs.vs_latest_vs = {
    url = "github:vapoursynth/vapoursynth";
    flake = false;
  };
  inputs.vs_latest_zimg = {
    url = "github:sekrit-twc/zimg/v3.0";
    flake = false;
  };

  # VS R57
  inputs.vs_57_vs = {
    url = "github:vapoursynth/vapoursynth/R57";
    flake = false;
  };
  inputs.vs_57_zimg = {
    url = "github:sekrit-twc/zimg/v3.0";
    flake = false;
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, ... }@releases:
    let
      default_python = "310";

      latest_is_version = 58;
      py_versions = [ "39" "310" ];
      vs_versions = [ 57 "latest" ];

      module = pkgs: vapoursynth: ps: ps.buildPythonPackage rec {
        pname = "vsengine";
        version = "r" + (pkgs.lib.strings.sanitizeDerivationName (builtins.readFile ./VERSION));
        pversion = pkgs.lib.removePrefix "r" version;
        format = "pyproject";
        src = ./.;
        buildInputs = [ ps.poetry ps.setuptools vapoursynth ps.trio ps.timeout-decorator ];
      };
    in
    {

    } // (flake-utils.lib.eachSystem [ "x86_64-linux" ] (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        findForRelease = release:
          let
            prefix = "vs_${toString release}_";
            filtered = pkgs.lib.filterAttrs (k: v: pkgs.lib.hasPrefix prefix k) releases;
          in
          pkgs.lib.mapAttrs' (k: v: { name = pkgs.lib.removePrefix prefix k; value = v; }) filtered;

        makeVapourSynthPackage = release: ps: 
          let
            sources = findForRelease release;

            zimg = pkgs.zimg.overrideAttrs (old: {
              src = sources.zimg;
            });

            vapoursynth = (pkgs.vapoursynth.overrideAttrs (old: {
              # Do not override default python.
              # We are rebuilding the python module regardless, so there
              # is no need to recompile the vapoursnyht module.
              src = sources.vs;
              version = "r" + toString (if release == "latest" then latest_is_version else release) + "";
              configureFlags = "--disable-python-module" + (if old ? configureFlags then old.configureFlags else "");
            })).override { zimg = zimg; };
          in
          ps.buildPythonPackage {
            pname = "vapoursynth";
            inherit (vapoursynth) src version;
            pversion = pkgs.lib.removePrefix "r" vapoursynth.version;
            buildInputs = [ ps.cython vapoursynth ];
            checkPhase = "true";
          };

        env = release: python: pkgs.poetry2nix.mkPoetryEnv {
          inherit python;

          projectDir = ./.;
          overrides = pkgs.poetry2nix.overrides.withDefaults (self: super: {
            vapoursynth = makeVapourSynthPackage release self;
          });
          extraPackages = (ps: [
            ps.ipython
          ]);
        };

        makeTest = vapoursynth: py_version: pkgs.runCommand "test_py${toString py_version}_vs${toString vapoursynth}_run" {} (
          let 
            python = pkgs."python${py_version}";
            moduleVs = makeVapourSynthPackage vapoursynth;
            py = python.withPackages (ps: with ps; [
              (module pkgs (moduleVs ps) ps)
              (moduleVs ps)

              trio
              timeout-decorator
            ]);
          in 
          ''
            touch $out
            ${pkgs.coreutils}/bin/timeout 30 ${py}/bin/python -m unittest discover -v -s ${./tests}
          ''
        );
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            pkgs."python${default_python}".pkgs.poetry
            poetry2nix
            (env 57 pkgs."python${default_python}")
          ];
        };

        checks = builtins.listToAttrs (map (v: {
          name = "py${v.py_versions}_vs${toString v.vs_versions}";
          value = makeTest v.vs_versions v.py_versions;
        }) (pkgs.lib.cartesianProductOfSets { inherit py_versions vs_versions; }));
      }));
}
