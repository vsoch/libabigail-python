# A Logic Program to work with Spack

The file [abi-facts.lp](abi-facts.lp) is generated with [this branch](https://github.com/vsoch/spack/tree/add/clingo-analyzer) of spack, which has an added analyzer for clingo:

```bash
$ spack install zlib+debug
$ spack install tcl+debug
$ spack analyze run  -a clingo tcl
```

Note above that both tcl and it's dependency zlib were installed with debug information,
otherwise this would not work. Also note that in the command above, we are stating
that "tcl" is the main library we are interested in to assess compatibility with
it's dependencies. In the case of generating facts for a solver (likely for a splice)
the problem will be slightly different - we will still be interested in some primary package,
but we will be including facts (atoms) for the dependency version we want to splice in.

The above command generates that file in the analyzers folder, in the clingo subdirectory. We are copying it here so it's easy to develop with.
Next, let's build a container to develop in:

```bash
$ docker build -f Dockerfile.clingo -t clingo-docker .
```

And shell into it.

```bash
$ docker run -it --rm -v $PWD/:/code clingo-docker bash
```

Unlike our first attempt in the [python](../python) folder, instead of having
a main binary and two libraries (one known to work and one we are testing),
for this logic program we are throwing all symbols in the space into a bag,
including the compiler, and we target the binaries of the main package as the 
ones we are interested in to assess if they still work. This means that we assume
that a dependency of this main library (that is already installed) is working,
and we don't add all nested dependency symbols into the mix. If any symbol is
missing for a main binary/library that we are interested in, we will throw an issue.

We can then develop and run our program:

```bash
(clingo-env) root@12069473da65:/code/python# clingo --out-ifs=\\n abi-facts.lp is_compatible.lp 
```
