# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2

{ lib, ... }:
let strace = (import ./debug.nix { inherit lib; }).strace;
in
rec {
  versions-to-name = prefix: version-map:
    let
      dynamicParts = lib.mapAttrsToList (k: v: "${k}${toString v}") version-map;
      allParts = [prefix] ++ dynamicParts;
    in
    builtins.concatStringsSep "-" allParts;

  each-version = what: lib.cartesianProductOfSets what;

  version-matrix = what: prefix: func: 
    builtins.listToAttrs (map (versions: {
      name = versions-to-name prefix versions;
      value = func versions;
    }) (each-version what));

  version-matrix-with-default = what: defaults: prefix: func:
    let
      matrix = version-matrix what prefix func;
    in 
    matrix // { 
      default = matrix."${versions-to-name prefix defaults}";
    };

  __version-builders = what: defaults: mapper:
    let
      run-func-with-mapper = func: versions: (mapper func) versions;
    in
    {
      build = prefix: func: version-matrix what prefix (run-func-with-mapper func);
      build-with-default = prefix: func: version-matrix-with-default what defaults prefix (run-func-with-mapper func);

      versions = each-version what;
      passed-versions = lib.mapAttrsToList (k: v: v) (version-matrix what "unused" (run-func-with-mapper (versions: versions)));

      map = next-mapper: __version-builders what defaults (f: next-mapper (mapper f));
      map-versions = version-mapper: __version-builders what defaults (f: versions: (mapper f) (version-mapper versions));
    };

  version-builders = what: defaults: __version-builders what defaults (f: f);
}
