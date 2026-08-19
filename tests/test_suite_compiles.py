"""Keep syntax errors out of the test and source trees."""

import compileall


def test_tests_and_src_compile():
    assert compileall.compile_dir("tests", quiet=1)
    assert compileall.compile_dir("src", quiet=1)
