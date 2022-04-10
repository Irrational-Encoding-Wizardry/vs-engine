import unittest

import vapoursynth as vs
from vapoursynth import core

from vsengine._testutils import forcefully_unregister_policy, use_standalone_policy
from vsengine.policy import Policy, GlobalStore

from vsengine._helpers import use_inline, wrap_variable_size


class TestUseInline(unittest.TestCase):
    def setUp(self) -> None:
        forcefully_unregister_policy()

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    def test_with_standalone(self):
        use_standalone_policy()
        with use_inline("test_with_standalone", None):
            pass

    def test_with_set_environment(self):
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    with use_inline("test_with_set_environment", None):
                        pass

    def test_fails_without_an_environment(self):
        with Policy(GlobalStore()):
            with self.assertRaises(EnvironmentError):
                with use_inline("test_fails_without_an_environment", None):
                    pass

    def test_accepts_a_managed_environment(self):
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with use_inline("test_accepts_a_managed_environment", env):
                    self.assertEqual(env.vs_environment, vs.get_current_environment())


    def test_accepts_a_standard_environment(self):
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with use_inline("test_accepts_a_standard_environment", env.vs_environment):
                    self.assertEqual(env.vs_environment, vs.get_current_environment())


class TestWrapVariable(unittest.TestCase):
    def setUp(self) -> None:
        forcefully_unregister_policy()
        use_standalone_policy()

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    def test_wrap_variable_bypasses_on_non_variable(self):
        bc = core.std.BlankClip()
        def _wrapper(c):
            self.assertIs(c, bc)
            return c
        wrap_variable_size(bc, bc.format, _wrapper)

    def test_wrap_caches_different_formats(self):
        bc24 = core.std.BlankClip(length=2)
        bc48 = core.std.BlankClip(format=vs.RGB48, length=2)
        sp = core.std.Splice([bc24, bc48, bc24, bc48], mismatch=True)

        counter = 0
        def _wrapper(c):
            nonlocal counter
            counter += 1
            return c.resize.Point(format=vs.RGB24)

        wrapped = wrap_variable_size(sp, vs.RGB24, _wrapper)
        for f in wrapped.frames():
            self.assertEqual(int(f.format), vs.RGB24)

        self.assertEqual(counter, 2)
        self.assertEqual(int(wrapped.format), vs.RGB24)

    def test_wrap_caches_different_sizes(self):
        bc1 = core.std.BlankClip(length=2, width=2, height=2)
        bc2 = core.std.BlankClip(length=2, width=4, height=4)
        sp = core.std.Splice([bc1, bc2, bc1, bc2], mismatch=True)

        counter = 0
        def _wrapper(c):
            nonlocal counter
            counter += 1
            return c.resize.Point(format=vs.RGB24)

        wrapped = wrap_variable_size(sp, vs.RGB24, _wrapper)
        for f in wrapped.frames():
            self.assertEqual(int(f.format), vs.RGB24)
        self.assertEqual(counter, 2)
        self.assertEqual(int(wrapped.format), vs.RGB24)

    def test_wrap_stops_caching_once_size_exceeded(self):
        bcs = [core.std.BlankClip(length=1, width=x, height=x) for x in range(1, 102)]
        assert len(bcs) == 101
        sp = core.std.Splice([*bcs, *bcs], mismatch=True)

        counter = 0
        def _wrapper(c):
            nonlocal counter
            counter += 1
            return c.resize.Point(format=vs.RGB24)

        wrapped = wrap_variable_size(sp, vs.RGB24, _wrapper)
        for _ in wrapped.frames():
            pass

        self.assertGreaterEqual(counter, 101)

