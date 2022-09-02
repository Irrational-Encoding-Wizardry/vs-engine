import os
import sys
import unittest
import subprocess


DIR = os.path.dirname(__file__)
PATH = os.path.join(DIR, "fixtures")


def run_fixture(fixture: str, expect_status: int = 0):
    path = os.path.join(PATH)
    if "PYTHONPATH" in os.environ:
        path += os.pathsep + os.environ["PYTHONPATH"]
    else:
        path += os.pathsep + os.path.abspath(os.path.join(".."))

    print(repr(path), file=sys.stderr)

    process = subprocess.run(
        [sys.executable, "-m", "vsengine.unittest", fixture],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env={
            "PYTHONPATH": path
        }
    )
    if process.returncode != expect_status:
        print(process.stdout.decode(sys.getdefaultencoding()), file=sys.stderr)
        assert False

class TestUnittestWrapper(unittest.TestCase):
    
    def test_core_in_module(self):
        run_fixture("unittest_core_in_module", 1)

    def test_stored_in_test(self):
        run_fixture("unittest_core_stored_in_test", 2)

    def test_succeeds(self):
        run_fixture("unittest_core_succeeds", 0)

