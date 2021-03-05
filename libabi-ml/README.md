# Libabi ML

This is an effort to "flatten" an abi corpus, with the intention to save to a "ML-friendly"
format, likely just a comma separated file. We will start with a json export generated
by the [wrapper](../wrapper) exercise. We will also explore the different fields (components)
of ABI with these resources:

 - [](https://refspecs.linuxbase.org/elf/TIS1.1.pdf)
 - [](https://www.uclibc.org/docs/psABI-x86_64.pdf)
 - [](http://www.sco.com/developers/devspecs/gabi41.pdf)


## Libabigail Structure

Exported to json, we have to keep in mind that the physical ordering of elements is
different, along with the structure (json expects groups in a list, xml can have arbitrary elements
fall in line under the same parent element). But if we are doing ML on the corpus
and using the elements as features, I think the ordering wouldn't be the most important
thing.


### Usage

The script accepts a single json file input generated from the [wrapper](../wrapper)
example:

```bash
$ python libabigail_to_features.py libabigail.json
```

You will see a printout of "unique" values for the elf symbols and functions,
and abi instruction groups:

```python
{'elf-function-symbol_@type': {'func-type'},
 'elf-function-symbol_@binding': {'global-binding', 'weak-binding'},
 'elf-function-symbol_@visibility': {'default-visibility'},
 'elf-function-symbol_@is-defined': {'yes'},
 'elf-variable-symbol_@type': {'object-type'},
 'elf-variable-symbol_@binding': {'global-binding', 'weak-binding'},
 'elf-variable-symbol_@visibility': {'default-visibility'},
 'elf-variable-symbol_@is-defined': {'yes'},
 'abi-instr_@version': {'yes'},
 'abi-instr_@address-size': {'yes'},
 'abi-instr_@path': {'yes'},
 'abi-instr_@comp-dir-path': {'yes'},
 'abi-instr_@language': {'yes'}}
```

What I'm interested in is getting a basic list of "has" and "needs" - as a hypothesis
for features that would be needed to assess ABI compatability. If two binaries need
to work together, the list of "has" for one should match what the other needs.
It's a fairly simple idea, but maybe will get us started to create a subcorpora
that we can use to match things. I'm not sure if this is useful, but here is what I want
to try:


If necessary, build and run the container defined in the [Dockerfile](Dockerfile) for a working environment.

### 1. Development Environment
 
```bash
$ docker build -t libab .
```

And run, binding to the present working directory:

```bash
$ docker run -it --rm -v $PWD:/code libab bash
```

### 2. Generate libraries

Next we want to run the script [libabigail_to_features.py](libabigail_to_features.py)
It's going to:

 1. Generate an exported [libabigail-library.json](libabigail-library.json) for a library of interest.
 2. For each shared object file required, find it and do the same.
 3. Inspect declarations that are needed and compare to what is provided by other libraries.


```bash
$ python3 libabigail_to_features.py /usr/local/lib/libabigail.so
```

This is probably pretty dumb, but I wanted to try it.
