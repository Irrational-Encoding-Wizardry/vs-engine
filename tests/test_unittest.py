import os
import sys
import unittest
import subprocess


DIR = os.path.dirname(__file__)
PATH = os.path.join(DIR, "fixtures")


class TestUnittestWrapper(unittest.TestCase):
    
    def test_core_in_module(self):
        with self.assertRaisesRegex(expected_exception=subprocess.CalledProcessError, expected_regex="status 1"):
            subprocess.check_call(
                [sys.executable, "-m", "vsengine.unittest", os.path.join(PATH, "unittest_core_in_module.py")],
                stderr=subprocess.STDOUT,
                stdout=subprocess.DEVNULL
            )

    def test_stored_in_test(self):
        with self.assertRaisesRegex(expected_exception=subprocess.CalledProcessError, expected_regex="status 2"):
            subprocess.check_call(
                [sys.executable, "-m", "vsengine.unittest", os.path.join(PATH, "unittest_core_stored_in_test.py")],
                stderr=subprocess.STDOUT,
                stdout=subprocess.DEVNULL
            )

    def test_succeeds(self):
        subprocess.check_call(
            [sys.executable, "-m", "vsengine.unittest", os.path.join(PATH, "unittest_core_succeeds.py")],
            stderr=subprocess.STDOUT,
            stdout=subprocess.DEVNULL
        )
