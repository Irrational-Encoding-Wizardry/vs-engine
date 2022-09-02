import unittest
from vapoursynth import core


core.std.BlankClip


class TestCoreInModule(unittest.TestCase):

    def test_something(self):
        raise RuntimeError("We should not even get here.")
