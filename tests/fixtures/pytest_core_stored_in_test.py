import pytest
from vapoursynth import core


test = [0]


def test_fails_core_stored_in_text():
    test[0] = core.std.BlankClip()
