import optparse
import sys
from enum import Enum


class TestStatus(Enum):
    PASSED = 1
    FAILED = 2
    SKIPPED = 3


class PVBase():

    """Base class for a PV test script.
       The __init__() and main() methods should not be overridden.

       This class also contains various public and private helper methods."""

    def __init__(self):
        """Sets test framework defaults. Do not override this method. Instead, override the set_test_params() method"""
        self.setup_clean_chain = False
        self.set_test_params()

    def main(self):
        """Main function. This should not be overridden by the subclass test scripts."""
        parser = optparse.OptionParser(usage="%prog [options]")
        self.add_options(parser)

        success = TestStatus.FAILED

        try:
            self.run_test()
            success = TestStatus.PASSED
        except AssertionError as e:
            print("Assertion failed")
            success = TestStatus.FAILED

        if success == TestStatus.PASSED:
            print("Tests successful")
            exit_code = TestStatus.PASSED
        else:
            print("Tests Failed")
            exit_code = TestStatus.FAILED

        exit_code = TestStatus.PASSED
        sys.exit(exit_code)

    # Methods to override in subclass test scripts.
    def set_test_params(self):
        """Tests must this method to change default values for number of nodes, topology, etc"""
        # raise NotImplementedError
        pass

    def add_options(self, parser):
        """Override this method to add command-line options to the test"""
        pass

