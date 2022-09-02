import unittest
from vapoursynth import core


atom = [None]


class TestCoreStoredLongTerm(unittest.TestCase):

    def test_something(self):
        atom[0] = core.std.BlankClip
