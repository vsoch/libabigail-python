# abi-python

Here I want to make an attempt to start and think about what it means for something to
be ABI compatible. This means that we will need to:

1. Create a toy project that can be assessed, meaning a simple application and two libraries (one compatible, and one not)
2. Generate output for libabigail, including a corpuses and a diff. We will attempt to re-create this output with Python. 
3. Start writing up what it means to be ABI compatible. We will want to eventually map this to checks we can do in code/logic.
4. Dump a corpora into logic statements (called atoms). We will want to combine this with logic statements about ABI compatability to hand to a solver.

## 1. Toy Project

Let's start with an application that is compiled with an initial library to generate
a simple math program. This is in the folder [simple-example](simple-example)
and can be compiled with g++ as follows:

```bash
make
```

## 2. Abidw, Abidiff, and Abicompat

The makefile also generates a slightly modified version of the library (which we don't
link against the app). The goal will be to use abicompat to show they aren't compatible.
Since we don't have libabigail locally, we can again build and spin up a container to generate
some output files.

```bash
$ docker build -t abigail .
```

Then run the container, binding the present working directory where we compiled
the example so we can run abidw on it.

```bash
$ docker run -it --rm -v $PWD/:/code abigail bash
```

Generate libabigail output.

```bash
$ cd simple-example/
# which abidw
/usr/local/bin/abidw
$ abidw 
```

I don't think we can output xml for an abidiff, but we can see what libabigail says is different:

```bash
# abidiff libmath-v1.so libmath-v2.so --dump-diff-tree
Functions changes summary: 1 Removed, 0 Changed, 1 Added functions
Variables changes summary: 0 Removed, 0 Changed, 0 Added variable

1 Removed function:

  [D] 'method double MathLibrary::Arithmetic::Add(double)'    {_ZN11MathLibrary10Arithmetic3AddEdd}

1 Added function:

  [A] 'method int MathLibrary::Arithmetic::Add(int)'    {_ZN11MathLibrary10Arithmetic3AddEii}
```

We can't get xml for abicompat either, but if we run it against the two libraries we get the
same answer:

```bash
# abicompat math-client libmath-v1.so libmath-v2.so 
ELF file 'math-client' is not ABI compatible with 'libmath-v2.so' due to differences with 'libmath-v1.so' below:
Functions changes summary: 1 Removed, 0 Changed, 0 Added function
Variables changes summary: 0 Removed, 0 Changed, 0 Added variable

1 Removed function:

  [D] 'method double MathLibrary::Arithmetic::Add(double)'    {_ZN11MathLibrary10Arithmetic3AddEdd}
```

This isn't hugely complicated, but it's a place to start!

## 3. Logic Program

We next want to be able to use the start of work from [corpus.py](corpus.py)
to dump out the corpora for each into a set of facts. Once we have these facts, we can start to work
on rules that indicate ABI compatability (or actually, not, because we can theoretically stop as soon as we find a reason
something is not). For this purpose, we are going to want to use clingo and the
python wrapper to interact with it, so we will again use a container. We need to install
the Python bindings for clingo, along with ipython (for easier development):

```bash
$ docker build -f Dockerfile.clingo -t clingo .
```

We are going to use a combination of spack's solver [asp.py](https://github.com/spack/spack/blob/develop/lib/spack/spack/solver/asp.py)
and [corpus.py](corpus.py) to try and accomplish the same.

```bash
$ docker run -it --rm -v $PWD/:/code clingo bash
```

We can then use the `is_compatible` function in [asp.py](asp.py) to develop.
Note that I installed ipython in the container too because it's nice to work with.
We can then develop by way of asking if our second library is compatible with the
first application (it should be).

```python
# /code is our present working directory
from asp import is_compatible
result = is_compatible("simple-example/math-client", "simple-example/libmath-v1.so")
```

**under development**

## 4. Rules

I'm going to start out by writing out a list of rules that determine ABI compatibility,
and we will want to have these represented in actual rules for the solver.
See [rules.md](rules.md) for this development.
