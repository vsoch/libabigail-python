# Libabigail Python Wrapper

This is a more reasonable / easy approach to wrap the abidw executable and
then parse into Python.

## Building the Container

First, let's build an interactive environment to develop and test.
It will have Python and Libabigail installed.

```bash
$ docker build -t libab-python .
```

You can then shell into the container to interact with python or libabigail.

```bash
$ docker run -it --rm libab-python bash
```

If you want to bind the code directory (to write files and work interactively)
you can do:

```bash
$ docker run -it --rm -v $PWD:/code libab-python bash
```

Once inside, you should be able to find the libabigail tools on your path.

```bash
which abidw
```

And test that they work!

```bash
$ abidw /usr/local/lib/libabigail.so
```

Very meta :)


## Usage

### abidw

The small script included, [abi_parser.py](abi_parser.py) is going to expect
to find this executable on the path, and use it. We actually want to use classes
from it. For example:

```python
from abi_parser import LibabigailWrapper
cli = LibabigailWrapper()
abi_dict = cli.abidw("/usr/local/lib/libabigail.so")
/usr/local/bin/abidw /usr/local/lib/libabigail.so
```

The structure of the xml is maintained.

```python
abi_dict.keys()
odict_keys(['abi-corpus'])

abi_dict['abi-corpus'].keys()
odict_keys(['@path', '@architecture', '@soname', 'elf-needed', 'elf-function-symbols', 'elf-variable-symbols', 'abi-instr'])
```

The resulting dictionary can be saved to file. To make this easy, the client has a
supporting function:

```python
cli.save_json(abi_dict, "examples/libabigail.json")
```

This file is HUGE (~177MB) so it's saved here as [libabigail.zip](examples/libabigail.zip).
Let's try a smaller one we can save as json:

```python
abi_dict = cli.abidw("/usr/lib/python3.8/lib-dynload/mmap.cpython-38-x86_64-linux-gnu.so")
cli.save_json(abi_dict, "examples/python-mmap.json")
```

You can see the [example](examples/python-mmap.json) for the above in the examples folder.
I can add other commands here if they are needed (with examples would be helpful to develop).
