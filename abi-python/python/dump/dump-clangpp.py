#!/usr/bin/env python3
from asp import generate_facts

generate_facts(
    [
        "../simple-example/clangpp/math-client",  # the binary
        "../simple-example/clangpp/libmath-v1.so",  # the known to work library
        "../simple-example/clangpp/libmath-v2.so",  # the unknown to work library
    ]
)
