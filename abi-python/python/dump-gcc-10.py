#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/c-gcc-10/math-client",  # the binary
        "../simple-example/c-gcc-10/libmath-v1.so",  # the known to work library
        "../simple-example/c-gcc-10/libmath-v2.so",  # the unknown to work library
    ]
)
