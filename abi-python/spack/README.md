# A Logic Program to work with Spack

The files `abi-facts*` are generated with [this branch](https://github.com/vsoch/spack/tree/add/clingo-analyzer) of spack, which has an added analyzer for clingo:

```bash
$ spack install zlib+debug
$ spack install tcl+debug
$ spack analyze run -a clingo --overwrite tcl
```

Note above that both tcl and it's dependency zlib were installed with debug information,
otherwise this would not work. Also note that in the command above, we are stating
that "tcl" is the main library we are interested in to assess compatibility with
it's dependencies. In the case of generating facts for a solver (likely for a splice)
the problem will be slightly different - we will still be interested in some primary package,
but we will be including facts (atoms) for the dependency version we want to splice in.

The above command generates those files in the analyzers folder, in the clingo subdirectory. We are copying it here so it's easy to develop with.
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
we are, for each main binary built by the package of interest, we are throwing
it along with all the dependency symbols into a common space (including compiler)
and then we assess if the main package binary still works. We can do this, one
at a time, for each main binary and exit with failure "This won't work" when we discover
the first. We assume that a dependency of this main library (that is already installed) is working,
and we don't add all nested dependency symbols into the mix. If any symbol is
missing for a main binary/library that we are interested in, we will throw an issue.

We can then develop and run our program:

```bash
(clingo-env) root@12069473da65:/code/python# clingo --out-ifs=\\n is_compatible.lp abi-facts-libtdbc1.1.2.so.lp
```

Note that not all logic programs are included, as some are too big for GitHub.
