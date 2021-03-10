# abi-python

Here I want to make an attempt to use [pyelftools](https://github.com/eliben/pyelftools/blob/master/examples/dwarf_die_tree.py)
to perform the same kind of analysis afforded by [libabigail](https://sourceware.org/git/libabigail.git), but entirely in Python.
The reason is because I don't think libabigail exposes an API that is intuitive or easy enough for a developer
or data scientist to work with. If it really comes down to reading binary dwarf information into a Corpus
object and comparing the intersection, I don't think this should be so hard to do.

## Usage

The simplest use case is to read a binary (ELF) and return a corpus. We can
do this with the ABIParser.

```python
from abipython import ABIParser
parser = ABIParser()
```

We can then ask for a corpus:

```python
corpus = parser.get_corpus_from_elf(filename)
```

Currently, we don't parse the die (and this component is not finished). I'm
not sure how we are doing the ABI comparison so I'm not able to implement this.
However we can look at a corpus header and symbols:

```python
corpus = parser.get_corpus_from_elf(filename)

corpus.elfheader
{'e_ident': Container({'EI_MAG': [127, 69, 76, 70], 'EI_CLASS': 'ELFCLASS64', 'EI_DATA': 'ELFDATA2LSB', 'EI_VERSION': 'EV_CURRENT', 'EI_OSABI': 'ELFOSABI_SYSV', 'EI_ABIVERSION': 0}),
 'e_type': 'ET_DYN',
 'e_machine': 'EM_X86_64',
 'e_version': 'EV_CURRENT',
 'e_entry': 934544,
 'e_phoff': 64,
 'e_shoff': 63644640,
 'e_flags': 0,
 'e_ehsize': 64,
 'e_phentsize': 56,
 'e_phnum': 12,
 'e_shentsize': 64,
 'e_shnum': 40,
 'e_shstrndx': 39}

corpus.elfsymbols
{'': {'type': 'STT_FILE', 'binding': 'STB_LOCAL', 'visibility': 'STV_DEFAULT'},
 'abg-traverse.cc': {'type': 'STT_FILE',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFAULT'},
 '_ZN7abigail2ir16traversable_baseC2Ev.cold': {'type': 'STT_FUNC',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFAULT'},
 'abg-ir.cc': {'type': 'STT_FILE',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFAULT'},
 '_ZNK7abigail2ir9decl_base15get_scoped_nameEv.localalias': {'type': 'STT_FUNC',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFAULT'},
 '_ZN7abigail2ir19ir_traversable_base8traverseERNS0_15ir_node_visitorE.localalias': {'type': 'STT_FUNC',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFAULT'},
 '_ZNK7abigail2ir9decl_base8get_hashEv.cold': {'type': 'STT_FUNC',
  'binding': 'STB_LOCAL',
  'visibility': 'STV_DEFA
...
```

I'm not sure if this will be useful or if it was just a learning exercise for me.
