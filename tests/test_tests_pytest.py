import os
import sys
import platform
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

    env = {**os.environ, "PYTHONPATH" : path}

    process = subprocess.run(
        [sys.executable, "-m", "pytest", os.path.join(PATH, f"{fixture}.py"), "-o", "cache_dir=/build/.cache"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env=env
    )
    if process.returncode != expect_status:
        print()
        print(process.stdout.decode(sys.getdefaultencoding()), file=sys.stderr)
        print()
        assert False, f"Process exited with status {process.returncode}"


class TestUnittestWrapper(unittest.TestCase):
    
    def test_core_in_module(self):
        run_fixture("pytest_core_in_module", 2)

    def test_stored_in_test(self):
        run_fixture("pytest_core_stored_in_test", 1)

    def test_succeeds(self):
        run_fixture("pytest_core_succeeds", 0)

