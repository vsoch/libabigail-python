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

Here is how I'm dumping a bunch of facts to look at:

```python
$ python dump.py > facts.lp
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

## 4. Figuring out Rules

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

At the onset of parsing, I don't know that the client needs this library. How
do I figure that out? Here we see it's referenced in a DIE for the math client:

```lp
DW_TAG_subprogram_attr("/code/simple-example/math-client:94","DW_AT_linkage_name","_ZN11MathLibrary10Arithmetic8SubtractEdd").
```

and for the library itself:

```lp
DW_TAG_subprogram_attr("/code/simple-example/libmath-v1.so:6","DW_AT_linkage_name","_ZN11MathLibrary10Arithmetic8SubtractEdd").
```

**Update**: @tgamblin suggested using libabigail xml for this task, but we cannot
at this point because it does not include undefined symbols. For the time being,
I added symbol_definition to say if a symbol is defined/undefined, and
we can use that to try and write a logic program. I also added in the third library
because it became clear that we could never know the set of symbols that are supposed
to be provided, and these are the `needed_symbol` groups. Now I'm working on writing logic in [is_compatible.lp](is_compatible.lp)
to first derive this set of needed symbols. After that, I'll look at [compute_diff](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L11031) in libabigail to derive more rules after that.

See [rules.md](rules.md) for breaking down this function in libabigail, and also
the logic in glibc. In the facts,
I'm currently at having a check over symbols and for just one architecture. It's pretty
limited but it's a start!

```bash
(clingo-env) root@12069473da65:/code/python# clingo --out-ifs=\\n   facts.lp is_compatible.lp 
clingo version 5.4.0
Reading from facts.lp ...
is_compatible.lp:99:18-41: info: atom does not occur in any rule head:
  corpus_elf_soname(#Anon0,A)

Solving...
Answer: 1
architecture_count(1)
get_missing_symbols("_ZN11MathLibrary10Arithmetic3AddEdd")
soname_count(0)
total_missing(1)
SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.005s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.005s
```

Based on writing this test case, that symbol is the one I expected to be not
compatible. We changed the input arguments from float to int. But now let's try the
C example, where we know the mangled strings don't include the variable
types (e.g., it would just be `Add`):

```bash
$ python dump-c.py > facts-c.lp
clingo --out-ifs=\\n   facts-c.lp is_compatible.lp 

is_compatible.lp:99:18-41: info: atom does not occur in any rule head:
  corpus_elf_soname(#Anon0,A)

Solving...
Answer: 1
architecture_count(1)
soname_count(0)
total_missing(0)
SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.004s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.004s
```

Just as we expected! The libraries look compatible because the function
in question (the symbol) looks like this:

```
symbol("Add").
symbol_type("/code/simple-example/c/math-client-c","Add","FUNC").
symbol_version("/code/simple-example/c/math-client-c","Add","").
symbol_binding("/code/simple-example/c/math-client-c","Add","GLOBAL").
symbol_visibility("/code/simple-example/c/math-client-c","Add","DEFAULT").
symbol_definition("/code/simple-example/c/math-client-c","Add","UND").
has_symbol("/code/simple-example/c/math-client-c","Add").
```

I think that we will need to dig into variable types and sizes (which we can derive
from the DIEs) next to address this.
