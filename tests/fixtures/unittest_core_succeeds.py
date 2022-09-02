import unittest
from vapoursynth import core


class TestCoreSucceeds(unittest.TestCase):

    def test_something(self):
        core.std.BlankClip().get_frame(0)
