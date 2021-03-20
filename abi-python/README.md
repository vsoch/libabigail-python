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
# you can also choose the c folder for a different use case
cd simple/example/cpp
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

There are now two approaches to this:

 - [python](python): attempts to parse the binaries directly and write out facts (this is currently suspented in favor of the next):
 - [xml](xml): generates those same facts directly from libabigail xml, the idea being that a lot of work already has been put into this representation so we should use it.
