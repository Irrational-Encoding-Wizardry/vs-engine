import pytest
from vapoursynth import core


def test_core_succeeds():
    core.std.BlankClip().get_frame(0)
