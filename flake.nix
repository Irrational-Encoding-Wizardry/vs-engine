{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  ####
  # This is for our test matrix.

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
  inputs.vs_58_vs = {
    url = "github:vapoursynth/vapoursynth/R58";
    flake = false;
  };
  inputs.vs_58_zimg = {
    url = "github:sekrit-twc/zimg/v3.0";
    flake = false;
  };

  outputs = { self, nixpkgs, flake-utils,  ... }@releases:
    let
      # Default versions for development.
      defaults = {
        python = "310";
        vapoursynth = "latest";
      };

      # Supported versions
      versions = {
        python = [ "39" "310" ];
        vapoursynth = [ 57 58 "latest" ];
      };

      # Version-Numbers for versions like "latest"
      aliases = {
        vapoursynth = {
          latest = 59;
        };
      };
    in
    flake-utils.lib.eachSystem [ "x86_64-linux" "x86_64-darwin" ] (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnsupportedSystem = true;
            allowBroken = true;
          };
        };

        lib = pkgs.lib;

        findForRelease = release:
          let
            prefix = "vs_${toString release}_";
            filtered = lib.filterAttrs (k: v: lib.hasPrefix prefix k) releases;
          in
          lib.mapAttrs' (k: v: { name = lib.removePrefix prefix k; value = v; }) filtered;

        makeVapourSynthPackage = release: ps: 
          let
            sources = findForRelease release;

            zimg = pkgs.zimg.overrideAttrs (old: {
              src = sources.zimg;
            });

            vapoursynth = (pkgs.vapoursynth.overrideAttrs (old: {
              # Do not override default python.
              # We are rebuilding the python module regardless, so there
              # is no need to recompile the vapoursynth module.
              src = sources.vs;
              version = "r" + toString (if (builtins.hasAttr (toString release) aliases.vapoursynth) then aliases.vapoursynth."${release}" else release) + "";
              configureFlags = "--disable-python-module" + (lib.optionalString (old ? configureFlags) old.configureFlags);
              preConfigure = ''
                ${# Darwin requires special ld-flags to compile with the patch that implements vapoursynth.withPlugins.
                  # we 
                  lib.optionalString (pkgs.stdenv.isDarwin) ''
                  export LDFLAGS="-Wl,U,_VSLoadPluginsNix''${LDFLAGS:+ ''${LDFLAGS}}"
                ''}
                ${lib.optionalString (old ? preConfigure) old.preConfigure}
              '';
            })).override { zimg = zimg; };
          in
          ps.buildPythonPackage {
            pname = "vapoursynth";
            inherit (vapoursynth) src version;
            pversion = lib.removePrefix "r" vapoursynth.version;
            buildInputs = [ ps.cython vapoursynth ];
            checkPhase = "true";
          };

        flib = import ./nix/lib pkgs;

        matrix = (flib.version-builders versions defaults).map-versions (versions: rec {
          python = pkgs."python${versions.python}";
          vapoursynth = makeVapourSynthPackage versions.vapoursynth python.pkgs;
          build-name = prefix: flib.versions-to-name prefix versions;
        });
      in
      rec {
        packages =
          let
            package-matrix = matrix.build-with-default "vsengine"
              (versions: versions.python.pkgs.buildPythonPackage rec {
                pname = "vsengine";
                pversion = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
                version = "r${lib.replaceStrings ["+"] ["_"] pversion}";
                format = "flit";
                src = ./.;
                propagatedBuildInputs = let ps = versions.python.pkgs; in [ 
                  ps.trio ps.setuptools versions.vapoursynth 
                ];
              });
          in 
          package-matrix // {
            dist = pkgs.runCommandNoCC "dist" {
                FLIT_NO_NETWORK="1";
                SOURCE_DATE_EPOCH = "0";
                src = ./.;
            } (
              let
                versions = map (version-map: ''
                  ${version-map.python.pkgs.flit}/bin/flit build
                '') matrix.passed-versions;
                script = builtins.concatStringsSep "\n" versions;
              in
              ''
                mkdir $out
                cp -r $src/* .
                ${script}
                cp dist/* $out
              ''
            );
          };

        # Build shells with each vapoursynth-version / python-tuple
        devShells = matrix.build-with-default "devShell"
          (versions: pkgs.mkShell {
            buildInputs = [
              (versions.python.withPackages (ps: [
                ps.flit
                ps.trio
                versions.vapoursynth
              ]))

              (versions.python.withPackages (ps: [
                # ps.mkdocs-material
                ps.mkdocs
              ]))
            ];
          });

        checks = matrix.build "check"
          (versions: pkgs.runCommandNoCC (versions.build-name "check") {} 
            (let py = versions.python.withPackages (ps: [packages.${versions.build-name "vsengine"}]); in ''
              ${py}/bin/python -m unittest discover -s ${./tests} -v 
              touch $out
            ''));

        # Compat with nix<2.7
        devShell = devShells.default;
        defaultPackage = packages.default;
      });
}
