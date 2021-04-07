#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/icc/math-client",  # the binary
        "../simple-example/icc/libmath-v1.so",  # the known to work library
        "../simple-example/icc/libmath-v2.so",  # the unknown to work library
    ]
)
