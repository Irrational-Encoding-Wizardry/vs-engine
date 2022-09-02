import sys
from unittest.main import TestProgram
from vsengine.policy import Policy, GlobalStore
from vsengine._hospice import any_alive


class MultiCoreTestProgram(TestProgram):

    def __init__(self, *args, **kwargs):
        self._policy = Policy(GlobalStore())
        self._policy.register()
        super().__init__(*args, **kwargs)

    def _run_once(self):
        try:
            super().runTests()
        except SystemExit as e:
            return e.code
        else:
            return 0

    def parseArgs(self, argv: list[str]) -> None:
        self.argv = argv
        return super().parseArgs(argv)

    def runTests(self):
        with self._policy.new_environment() as e1:
            with e1.use():
                self._run_once()
        del e1

        if self.exit and not self.result.wasSuccessful():
            sys.exit(False)

        if any_alive():
            print("The core is still being used. This is a bad thing.", file=sys.stderr)
            sys.exit(2)

        super().parseArgs(self.argv)
        with self._policy.new_environment() as e2:
            with e2.use():
                self._run_once()
        del e2

        if any_alive():
            print("The core is still being used. This is a bad thing.", file=sys.stderr)
            sys.exit(2)


        if self.exit and not self.result.wasSuccessful():
            sys.exit(False)

        sys.exit(0)


def main():
    MultiCoreTestProgram(module=None)

if __name__ == "__main__":
    main()

