#!/usr/bin/env python3
from asp import is_compatible

# This will dump facts to the screen (for now)
#result = is_compatible(
#    "../simple-example/cpp/math-client", "../simple-example/cpp/libmath-v1.so"
#)


result = is_compatible(
    "../simple-example/cpp/math-client", "../simple-example/cpp/libmath-v1.so", logic_programs=['show_undefined.lp']
)

