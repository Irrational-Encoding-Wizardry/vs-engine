{ lib, ... }:
{
  strace = s: builtins.trace s s;
}
