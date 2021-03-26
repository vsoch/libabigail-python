#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/c/math-client-c",  # the binary
        "../simple-example/c/libmathc-v1.so",  # the known to work library
        "../simple-example/c/libmathc-v2.so",  # the unknown to work library
    ]
)
