# A Logic Program in Python

We next want to be able to use the start of work from [corpus.py](corpus.py)
to dump out the corpora for each into a set of facts. Once we have these facts, we can start to work
on rules that indicate ABI compatability (or actually, not, because we can theoretically stop as soon as we find a reason
something is not). For this purpose, we are going to want to use clingo and the
python wrapper to interact with it, so we will again use a container. We need to install
the Python bindings for clingo, along with ipython (for easier development):

```bash
$ docker build -f Dockerfile.clingo -t clingo-docker .
```

We are going to use a combination of spack's solver [asp.py](https://github.com/spack/spack/blob/develop/lib/spack/spack/solver/asp.py)
and [corpus.py](corpus.py) to try and accomplish the same.

```bash
$ cd ..
$ docker run -it --rm -v $PWD/:/code clingo-docker bash
```

We can then use the `is_compatible` function in [asp.py](asp.py) to run the solver
with a file, and `generate_facts` to generate facts (what I'm doing for development).
Note that I installed ipython in the container too because it's nice to work with.
We are taking an approach similar to `abicompat` for libabigail, namely starting
with:

 - a binary
 - a library linked (known to work) with the binary
 - a second library in question (we want to know if it works)

The first library provides us with the set of symbols that we would need to 
match in the second library. Another strategy might be to read in the symbols
from the other libs in the elf needed section, but we are starting with an
approach to match libabigail for now. The function call with the libraries
looks like this:

```python
# /code/python is our present working directory
from asp import generate_facts

generate_facts([
    "../simple-example/cpp/math-client",  # the main binary
    "../simple-example/cpp/libmath-v1.so", # the library we know to work
    "../simple-example/cpp/libmath-v2.so" # the library we are curious about
])
```

The above is hard coded in a bunch of pre-written files in [dump](dump)
to make it easy to run for different compilers.
Here is how I'm dumping a bunch of facts to look at:

```python
$ python dump/cpp.py > facts/facts.lp
```
The facts have headers, and for the most part it's fairly straight forward.
The symbols in the "known to work" library that we need to match in the
library of question look like the following:

```lp
%----------------------------------------------------------------------------
% Known needed symbols: /code/simple-example/cpp/libmath-v1.so
%----------------------------------------------------------------------------
symbol("__cxa_finalize").
needed_symbol("__cxa_finalize").
needed_symbol_type("__cxa_finalize","NOTYPE").
needed_symbol_version("__cxa_finalize","").
needed_symbol_binding("__cxa_finalize","WEAK").
needed_symbol_visibility("__cxa_finalize","DEFAULT").
needed_symbol_definition("__cxa_finalize","UND").
```

## 4. Figuring out Symbol Rules

Okay, the first thing I want to do is figure out what symbols the client needs,
vs. what symbols the library provides. From the source code we can take an example -
basically any of the Math Arithmetic functions are provided by libmath-v1.so,
and needed by MathClient.cpp. We can see both are identified in the elf-symbols
table. Here is for MathClient:

```lp
symbol("_ZN11MathLibrary10Arithmetic8SubtractEdd").
symbol_type("_ZN11MathLibrary10Arithmetic8SubtractEdd","STT_FUNC").
symbol_binding("_ZN11MathLibrary10Arithmetic8SubtractEdd","STB_GLOBAL").
symbol_visibility("_ZN11MathLibrary10Arithmetic8SubtractEdd","STV_DEFAULT").
has_symbol("/code/simple-example/math-client","_ZN11MathLibrary10Arithmetic8SubtractEdd").
```

and for the library it derives it from:

```lp
symbol("_ZN11MathLibrary10Arithmetic8SubtractEdd").
symbol_type("_ZN11MathLibrary10Arithmetic8SubtractEdd","STT_FUNC").
symbol_binding("_ZN11MathLibrary10Arithmetic8SubtractEdd","STB_GLOBAL").
symbol_visibility("_ZN11MathLibrary10Arithmetic8SubtractEdd","STV_DEFAULT").
has_symbol("/code/simple-example/libmath-v1.so","_ZN11MathLibrary10Arithmetic8SubtractEdd").
```

I was able to update [asp.py](asp.py) and [corpus.py](corpus.py) to determine
when we have missing symbols based on these facts.

**Update**: @tgamblin suggested using libabigail xml for this task, but we cannot
at this point because it does not include undefined symbols. For the time being,
I added symbol_definition to say if a symbol is defined/undefined, and
we can use that to try and write a logic program. I also added in the third library
because it became clear that we could never know the set of symbols that are supposed
to be provided, and these are the `needed_symbol` groups. 

## 4. Figuring out Generic Rules

See [rules.md](rules.md) for breaking down generic rules in libabigail, and also glibc. 


## 5. Figuring out Diffing for Types

It's clear that the core of libabigail is running `compute_diff` for many different types.
Instead of trying to go through the code files for libabigail in terms of execution, I want
to first walk through each of these functions and try to understand what is going on.
See [diffs.md](diffs.md) for this exercise.

## 6. is_compatible

I'm working on writing logic in [is_compatible.lp](is_compatible.lp)
to first derive this set of needed symbols.
We can see the current output below (for the C++) is able to:

1. Identify the missing symbol, and say there is 1 missing symbol
2. Count one architecture (correct)
3. No size or type mismatches
4. Clarify the main program (math-client), the working library (libmath-v1.so) and the one we are testing (libmath-v2.so).
5. See the rule that the parameter counts (between main and the library, for shared symbols) are equal.



```bash
(clingo-env) root@12069473da65:/code/python# clingo --out-ifs=\\n facts/facts.lp is_compatible.lp 
clingo version 5.4.0
Reading from facts/facts.lp ...
...
Solving...
Answer: 1
architecture_count(1)
count_missing_symbols(1)
count_subprogram_parameters_size_mismatch(0)
count_subprogram_parameters_type_mismatch(0)
get_architecture("EM_X86_64")
get_formal_parameter_count_library(3)
get_formal_parameter_count_main(3)
get_missing_symbols("_ZN11MathLibrary10Arithmetic3AddEdd")
is_library("/code/simple-example/cpp/libmath-v2.so")
is_main("/code/simple-example/cpp/math-client")
is_needed("/code/simple-example/cpp/libmath-v1.so")
formal_parameter_counts_equal(3,3)
SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.175s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.175s
```

Based on writing this test case, that symbol is the one I expected to be not
compatible. We changed the input arguments from float to int. But now let's try the
C example, where we know the mangled strings don't include the variable
types (e.g., it would just be `Add`). Before checking for types and sizes,
we would not identify any missing symbols because both are named "Add" despite
having different parameters. But now since we added types and sizes we can
see there is aboth a size and type mismatch:

```bash
$ python dump-c.py > facts/facts-c.lp
# clingo --out-ifs=\\n facts/facts-c.lp is_compatible.lp 
clingo version 5.4.0
Reading from facts/facts-c.lp ...
...

Solving...
Answer: 1
architecture_count(1)
count_missing_symbols(0)
count_subprogram_parameters_size_mismatch(1)
count_subprogram_parameters_type_mismatch(1)
get_architecture("EM_X86_64")
get_formal_parameter_count_library(1)
get_formal_parameter_count_main(0)
is_library("/code/simple-example/c/libmath-v2.so")
is_main("/code/simple-example/c/math-client")
is_needed("/code/simple-example/c/libmath-v1.so")
library_formal_parameters("/code/simple-example/c/libmath-v2.so","0d4da1237a945ffc1d5e421ffd5752e3","Add","9382a504b9272595542486c61a7affb0")
library_formal_parameters("/code/simple-example/c/libmath-v2.so","0d4da1237a945ffc1d5e421ffd5752e3","Add","c83a9eccfcf01fe36ff19e1edacb0c91")

Models       : 1
Calls        : 1
Time         : 0.019s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.019s
```

## 7. Testing Different Compilers

I noticed that for the c version, the main-client doesn't seem to have the formal parameter, so in the
above we only see entries for the library. Chatting with Matt, this is a decision by the compiler.
I tested for the following compilers:

 - **g++**: does have entries
 - **gcc**: does not have entries
 - **gcc-10**: does not have entries
 - **icc**: does not have entries
 - **icpc**: does not have entries
 - **clang**: does not have entries
 - **clang-10**: does not have entries for 10.1, does have entries for 10.2 (bleeding edge!)
 - **clang++** looks like it has entries, but doesn't show up with same is_compatible.lp script.
