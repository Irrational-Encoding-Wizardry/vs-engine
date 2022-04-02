{ lib, ... }@pkgs:
lib.foldl' (p: n: p // n) {}
  (builtins.map (path: import path pkgs) [
    ./matrix.nix
    ./debug.nix
  ])
