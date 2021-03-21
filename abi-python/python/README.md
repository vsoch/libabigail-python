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
with a file, and `generate_facts` to generate facts.
Note that I installed ipython in the container too because it's nice to work with.

```python
# /code/python is our present working directory
from asp import generate_facts

generate_facts([
    "../simple-example/cpp/math-client",
    "../simple-example/cpp/libmath-v1.so"
])
```

Here is how I'm dumping a bunch of facts to look at:

```python
$ python dump.py > facts.lp
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

**Update**: I added symbol_definition to say if a symbol is defined/undefined, and
we can use that to try and write a program. I'm stuck at a point of running
clingo and having it tell me:

```bash
(clingo-env) root@b32e9108f711:/code/python# clingo facts.lp is_compatible.lp 
clingo version 5.4.0
Reading from facts.lp ...
is_compatible.lp:33:1-29: info: no atoms over signature occur in program:
  symbol_is_undefined/0

Solving...
Answer: 1

SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.004s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.004s
```

@tgamblin suggested using libabigail xml, but it doesn't have whether a symbol is
defined or not. 
