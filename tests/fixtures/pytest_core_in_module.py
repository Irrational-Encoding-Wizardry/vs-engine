import pytest
from vapoursynth import core


clip = core.std.BlankClip()


def test_should_never_be_run():
    import os
    try:
        os._exit(3)
    except AttributeError:
        import sys
        sys.exit(3)

