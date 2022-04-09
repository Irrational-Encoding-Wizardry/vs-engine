# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2

{ lib, ... }@pkgs:
lib.foldl' (p: n: p // n) {}
  (builtins.map (path: import path pkgs) [
    ./matrix.nix
    ./debug.nix
  ])
