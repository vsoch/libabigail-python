# abispack-lib

What does spack actually need from libabigail? Here we can outline a set of
functions, inputs and outputs, that spack would want to interact with libabigail,
and then to send some metadata to a monitor server (or otherwise use it
to drive a solver).

## Development Environment

Since we want to use libabigail.so, the easiest thing to do is provide an
equivalent development container. Build it first:

```bash
$ docker build -t abispack .
```

We will want to bind the code directory (to write files and work interactively):

```bash
$ docker run -it --rm -v $PWD/src:/code/src abispack bash
```

## Functions that we want

Ben noted that:

> I kind of think we don’t need a full set of bindings for all the libabigail functions.

And this is a great insight, because writing Python bindings for the entirety of libabigail
would be challenging, but writing bindings for a smaller library that _uses_ libabigail is not
as daunting. What we instead want is:

> a set of functions that can implement the functions that Spack needs.

And so this description is a start of thinking about this.

### Reading a corpus from ELF

Spack will want to ask libabigail to read a corpus from ELF, and return it.
Likely if we can expose that function in our application here, and then (in the binding
function) convert that information to json, it would be easy to hand off to spack.

```python
from abispack import read_corpus
corpus = read_corpus("pusheenalibrary.so")
```

### Write a corpus to abixml

We technically could have Spack call libabigail from the command line,
dump a result into an xml file, and then gzip that, but it would be better
if we could easily do this from spack (calling our application here):

```python
from abispack import write_corpus
success = write_xml_corpus("pusheenalibrary.so", gzip=True)
```

This would likely also accept an output file name, but default to the library plus extension needed (e.g., pusheenalibrary.gzip or pusheenalibrary.xml)
We might just want to require the output file so the directory is included too. :)

### Reading a corpus from abixml

Given that we have an exported corpus (per the function directly above) we would want
to be able to read it, and have the same corpus that we might have read with `read_corpus`.

```python
from abispack import read_abixml
corpus = read_abixml("pusheenacorpus.gzip")
```

As you can see above, the file being read could be compressed (or not).

### Make one or more subcorpus

Once we've identified what parts of the ABI output are important for
the application, we would then want Spack to be able to easily ask for them.

```python
from abispack import read_corpus
corpus = read_corpus("pusheenalibrary.so")
```

Actually, in this context, it might make sense to have a class to handle this,
like:

```python
from abispack import LibabigailParser
parser = LibabigailParser()
parser.read_corpus("pusheenalibrary.so")
subcorpus = parser.subcorpus() # probably need a more specific name here
```

We'd probably want arguments here to specify if we want to make subcorpus
groups from ELF and/or abixml, and then return them organized as such.

### Compatability

We'd want to have a class function that can wrap `abicompat` and then help us
determine if two binaries are compatible. Maybe like:

```python
from abispack import are_compatible
if are_abi_compatible(library1, library2):
    print("yay!")
```

We might want to distinguish between saying two things are compatible vs. saying
they are exactly the same.
