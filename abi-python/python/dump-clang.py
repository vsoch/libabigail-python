#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/clang/math-client",  # the binary
        "../simple-example/clang/libmath-v1.so",  # the known to work library
        "../simple-example/clang/libmath-v2.so",  # the unknown to work library
    ]
)
