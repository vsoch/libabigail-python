# A Logic Program from Libabigail

Instead of writing our own Dwarf/Elf parser, this route aims to just export
corpora with libabigail `abidw` and then generate facts from that. Let's again build
a container that has clingo and libabigail:


```bash
$ docker build -t clingo .
```

For all operations we will interactively shell into the container first.
Note that we are in the parent directory from this folder to have access
to the cpp/c simple applications:

```bash
$ cd ..
$ docker run -it --rm -v $PWD/:/code clingo bash
```


## 1. Generate ABI Corpora

If you haven't yet, make the binaries for each of cpp and c:

```bash
cd /code/simple-example/cpp
make

cd /code/simple-example/c
make
```

And now for the cpp to start, let's generate corpora in xml.

```bash
$ abidw /code/simple-example/cpp/math-client --out-file /code/simple-example/cpp/math-client.xml
$ abidw /code/simple-example/cpp/libmath-v1.so --out-file /code/simple-example/cpp/libmath-v1.xml
$ abidw /code/simple-example/c/math-client --out-file /code/simple-example/c/math-client.xml
$ abidw /code/simple-example/c/libmath-v1.so --out-file /code/simple-example/c/libmath-v1.xml
```

## 2. Generate Facts

We are going to use a a modified [libabigail_asp.py](https://github.com/spack/spack/blob/develop/lib/spack/spack/solver/asp.py) to run a `is_compatible` function on our xml:


```python
# /code/xml is our present working directory
from asp import is_compatible
result = is_compatible("../simple-example/cpp/math-client.xml", "../simple-example/cpp/libmath-v1.xml")
```

Here is how I'm dumping a bunch of facts to look at:

```python
$ python dump.py > facts.lp
```

## 4. Figuring out Rules

**under development**
