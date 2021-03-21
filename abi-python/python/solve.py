#!/usr/bin/env python3
from libabigail_asp import is_compatible

result = is_compatible(
    "../simple-example/cpp/math-client.xml",
    "../simple-example/cpp/libmath-v1.xml",
    logic_programs = "is_compatible.lp"
)
