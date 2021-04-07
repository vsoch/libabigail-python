#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/cpp/math-client",  # the binary
        "../simple-example/cpp/libmath-v1.so",  # the known to work library
        "../simple-example/cpp/libmath-v2.so",  # the unknown to work library
    ]
)
