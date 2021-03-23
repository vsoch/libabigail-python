# Corpus.py
# This is a script that will help me to develop a Corpus class, into which
# we can load an entire DIE tree. This is based on the elftools example:
# dwarf_die_tree.py. Specifically, if we inspect a binary, there are .debug_info
# sections with Dwarf Information Entries (referred to as "DIEs" that form
# a tree.

import elftools.construct.macros as macros
from elftools.elf.elffile import ELFFile, ELFError, NullSection
from elftools.elf.dynamic import DynamicSection, DynamicSegment
from elftools.common.py3compat import bytes2str
import sys
import enum
import os

from elftools.elf.sections import (
    NoteSection,
    SymbolTableSection,
    SymbolTableIndexSection,
)
from elftools.elf.gnuversions import (
    GNUVerSymSection,
    GNUVerDefSection,
    GNUVerNeedSection,
)

from elftools.elf.constants import SHN_INDICES
from elftools.elf.relocation import RelocationSection

from elftools.elf.descriptions import (
    describe_symbol_type,
    describe_symbol_bind,
    describe_symbol_visibility,
    describe_symbol_shndx,
)


__version__ = "1.0"


class CorpusReader(ELFFile):
    """A CorpusReader wraps an elffile, allowing us to easily open/close
    and keep the stream open while we are interacting with content. We close
    the file handle on any exit.
    """

    def __init__(self, filename):
        self.fd = open(filename, "rb")
        self.filename = filename
        try:
            self.elffile = ELFFile(self.fd)
        except:
            sys.exit("%s is not an ELF file." % filename)

        # Cannot continue without dwarf info
        if not self.elffile.has_dwarf_info():
            sys.exit("%s is missing DWARF info." % self.filename)
        self.get_version_lookup()
        self.get_shndx_sections()

    def __str__(self):
        return "[CorpusReader:%s]" % self.filename

    def __repr__(self):
        return str(self)

    @property
    def header(self):
        return dict(self.elffile.header)

    def __exit__(self):
        print("Closing reader")
        self.fd.close()

    def get_architecture(self):
        return self.elffile.header.get("e_machine")

    def get_elf_class(self):
        return self.elffile.elfclass

    def get_version_lookup(self):
        """Get versioning used (GNU or Solaris)
        https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py#L915
        """
        lookup = dict()
        types = {
            GNUVerSymSection: "versym",
            GNUVerDefSection: "verdef",
            GNUVerNeedSection: "verneed",
            DynamicSection: "type",
        }

        for section in self.elffile.iter_sections():
            if type(section) in types:
                identifier = types[type(section)]
                if identifier == "type":
                    for tag in section.iter_tags():
                        if tag["d_tag"] == "DT_VERSYM":
                            lookup["type"] = "GNU"
                else:
                    lookup[identifier] = section

        # If we don't have a type but we have verneed or verdef, it's solaris
        if not lookup.get("type") and (lookup.get("verneed") or lookup.get("verdef")):
            lookup["type"] = "Solaris"
        self._versions = lookup

    def get_shndx_sections(self):
        """I think this referes to section index/indices. We want a mapping
        from a symbol table index to a corresponding section object.
        """
        self._shndx_sections = {
            x.symboltable: x
            for x in self.elffile.iter_sections()
            if isinstance(x, SymbolTableIndexSection)
        }

    def get_symbols(self):
        """Return a set of symbols from the dwarf symbol tables"""
        symbols = {}

        # We want .symtab and .dynsym
        tables = [
            (idx, s)
            for idx, s in enumerate(self.elffile.iter_sections())
            if isinstance(s, SymbolTableSection)
        ]

        for idx, section in tables:
            # Symbol table has no entries if this is zero
            # section.num_symbols() shows count, section.name is name
            if section["sh_entsize"] == 0:
                continue

            # We need the index of the symbol to look up versions
            for sym_idx, symbol in enumerate(section.iter_symbols()):

                # Version info is from the versym / verneed / verdef sections.
                version_info = self._get_symbol_version(section, sym_idx, symbol)

                # We aren't considering st_value, which could be many things
                # https://docs.oracle.com/cd/E19683-01/816-1386/6m7qcoblj/index.html#chapter6-35166
                symbols[symbol.name] = {
                    "version_info": version_info,
                    "type": describe_symbol_type(symbol["st_info"]["type"]),
                    "binding": describe_symbol_bind(symbol["st_info"]["bind"]),
                    "visibility": describe_symbol_visibility(
                        symbol["st_other"]["visibility"]
                    ),
                    "defined": describe_symbol_shndx(
                        self._get_symbol_shndx(symbol, sym_idx, idx)
                    ).strip(),
                }

        return symbols

    def _get_symbol_version(self, section, sym_idx, symbol):
        """Given a section, symbol index, and symbol, return version info
        https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py#L400
        """
        version_info = ""

        # I'm not sure why this would be empty
        if not self._versions:
            return version_info

        # readelf doesn't display version info for Solaris versioning
        if section["sh_type"] == "SHT_DYNSYM" and self._versions["type"] == "GNU":
            version = self._symbol_version(sym_idx)
            if version["name"] != symbol.name and version["index"] not in (
                "VER_NDX_LOCAL",
                "VER_NDX_GLOBAL",
            ):

                # This is an external symbol
                if version["filename"]:
                    version_info = "@%(name)s (%(index)i)" % version

                # This is an internal symbol
                elif version["hidden"]:
                    version_info = "@%(name)s" % version
                else:
                    version_info = "@@%(name)s" % version
        return version_info

    def _symbol_version(self, idx):
        """We can get version information for a symbol based on it's index
        https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py#L942
        """
        symbol_version = dict.fromkeys(("index", "name", "filename", "hidden"))

        # No version information available
        if (
            not self._versions.get("versym")
            or idx >= self._versions.get("versym").num_symbols()
        ):
            return None

        symbol = self._versions["versym"].get_symbol(idx)
        index = symbol.entry["ndx"]
        if not index in ("VER_NDX_LOCAL", "VER_NDX_GLOBAL"):
            index = int(index)

            # GNU versioning means highest bit is used to store symbol visibility
            if self._versions["type"] == "GNU":
                if index & 0x8000:
                    index &= ~0x8000
                    symbol_version["hidden"] = True

            if (
                self._versions.get("verdef")
                and index <= self._versions["verdef"].num_versions()
            ):
                _, verdaux_iter = self._versions["verdef"].get_version(index)
                symbol_version["name"] = next(verdaux_iter).name
            else:
                verneed, vernaux = self._versions["verneed"].get_version(index)
                symbol_version["name"] = vernaux.name
                symbol_version["filename"] = verneed.name

        symbol_version["index"] = index
        return symbol_version

    def _get_symbol_shndx(self, symbol, symbol_index, symtab_index):
        """Every symbol table entry is defined in relation to some section.
        The st_shndx of a symbol holds the relevant section header table index.
        https://github.com/eliben/pyelftools/blob/master/scripts/readelf.py#L994
        """
        if symbol["st_shndx"] != SHN_INDICES.SHN_XINDEX:
            return symbol["st_shndx"]

        # Check for or lazily construct index section mapping (symbol table
        # index -> corresponding symbol table index section object)
        if self._shndx_sections is None:
            self._shndx_sections = {
                sec.symboltable: sec
                for sec in self.elffile.iter_sections()
                if isinstance(sec, SymbolTableIndexSection)
            }
        return self._shndx_sections[symtab_index].get_section_index(symbol_index)

    def get_dynamic_tags(self):
        """Get the dyamic tags in the ELF file."""
        tags = {}
        for section in self.elffile.iter_sections():
            if not isinstance(section, DynamicSection):
                continue

            # We are interested in architecture, soname, and needed
            def add_tag(section, tag):
                if section not in tags:
                    tags[section] = []
                tags[section].append(tag)

            for tag in section.iter_tags():
                if tag.entry.d_tag == "DT_NEEDED":
                    add_tag("needed", tag.needed)
                elif tag.entry.d_tag == "DT_RPATH":
                    add_tag("rpath", tag.rpath)
                elif tag.entry.d_tag == "DT_RUNPATH":
                    add_tag("runpath", tag.runpath)
                elif tag.entry.d_tag == "DT_SONAME":
                    tags["soname"] = tag.soname

            return tags

    def _iter_dwarf_information_entries(self):
        dwarfinfo = self.elffile.get_dwarf_info()

        # A CU is a Compilation Unit
        for cu in dwarfinfo.iter_CUs():

            # A DIE is a dwarf information entry
            for die in cu.iter_DIEs():
                yield die

    def iter_dwarf_information_entries(self):
        """We possibly want to return this in json (why defined as a separate
        function from _iter_dwarf_information_entries) although right now is
        just serving the same result!
        """
        for die in self._iter_dwarf_information_entries():
            yield die

    def parse_dwarf_entries(self):
        for die in self._iter_dwarf_information_entries():
            result = parse_children(die)


class Corpus:
    """A Corpus is an ELF file header combined with complete elf symbols,
    variables, and nested Dwarf Information Entries
    """

    def __init__(self, filename, include_dwarf_entries=False, load_needed_libs=True):
        self.elfheader = {}

        # This could be split into variables / symbols
        self.elfsymbols = {}
        self.path = filename
        self.dynamic_tags = {}
        self.architecture = None
        self._soname = None
        self.read_elf_corpus(include_dwarf_entries)

        # If we want a full set of symbols, we need elf needed loaded
        if load_needed_libs:
            self.load_elf_needed()

    def __str__(self):
        return "[Corpus:%s]" % self.path

    def __repr__(self):
        return str(self)

    def exists(self):
        return self.path is not None and os.path.exists(self.path)

    @property
    def soname(self):
        return self.dynamic_tags.get("soname")

    @property
    def needed(self):
        return self.dynamic_tags.get("needed", [])

    @property
    def runpath(self):
        return self.dynamic_tags.get("runpath")

    @property
    def rpath(self):
        return self.dynamic_tags.get("rpath")

    def iter_dwarf_information_entries(self):
        """Return flattened list of DIEs (Dwarf Information Entrys"""
        reader = CorpusReader(self.path)
        for entry in reader.iter_dwarf_information_entries():
            yield entry

    def load_elf_needed(self):
        """In order to find other undefined symbols, we might also need to
        load these other libraries that are used.
        """
        # TODO: if we don't want to provide a third binary, we could do this
        pass

    def read_elf_corpus(self, include_dwarf_entries=False):
        """Read the entire elf corpus, including dynamic and other sections
        expected for showing ABI information
        """
        reader = CorpusReader(self.path)

        # Read in the header section as part of the corpus
        self.elfheader = reader.header

        # Read in dynamic tags, and symbols
        self.dynamic_tags = reader.get_dynamic_tags()
        self.architecture = reader.get_architecture()
        self.elfclass = reader.get_elf_class()
        self.elfsymbols = reader.get_symbols()

        # Labeled as abi-instr in libabigail
        if include_dwarf_entries:
            abi_instr = reader.parse_dwarf_entries()


class ABIParser:
    """An ABIparser accepts a binary, which should be an elf file, and then
    exposes functions to return a corpus, compare corpora, or produce
    subcorpora.
    """

    def __init__(self):
        pass

    def __str__(self):
        return "[ABIParser]"

    def __repr__(self):
        return str(self)

    def get_corpus_from_elf(
        self, filename, include_dwarf_entries=False, load_needed_libs=True
    ):
        """
        Given an elf binary, read it in with elfutils ELFFile and then
        iterate through dwarf info to generate a tree.

        Arguments:
            filename (path): path to filename to get corpus for
            include_dwarf_entries (bool): parse dwarf entries (DIEs)
            load_needed_libs(bool): try to find and load needed libraries
        """
        filename = os.path.abspath(filename)
        if not os.path.exists(filename):
            sys.exit("%s does not exist." % filename)

        # Create a new corpus to interact with
        return Corpus(filename, include_dwarf_entries, load_needed_libs)


def get_die_filepath(die):
    filepath = None
    if "DW_AT_decl_file" in die.attributes:
        index = die.attributes["DW_AT_decl_file"].value

        # TODO: need to debug why this fails sometimes
        try:
            filepath = get_cu_filename(die.cu, index)
        except:
            pass
    return filepath


def get_cu_filename(cu, idx=0):
    """A DW_AT_decl_file I think can be looked up, by index, from the CU
    file entry and directory index.
    """
    lineprogram = cu.dwarfinfo.line_program_for_CU(cu)
    cu_filename = bytes2str(lineprogram["file_entry"][idx - 1].name)
    if len(lineprogram["include_directory"]) > 0:
        dir_index = lineprogram["file_entry"][idx - 1].dir_index
        if dir_index > 0:
            dir_name = bytes2str(lineprogram["include_directory"][dir_index - 1])
        else:
            dir_name = "."
        cu_filename = "%s/%s" % (dir_name, cu_filename)
    return cu_filename


def parse_compile_unit(die):
    """parse a compile unit (usually at the top). A compile unit (in xml) looks
    like the following:

    <abi-instr version='1.0' address-size='64'
               path='../../src/abg-regex.cc' comp-dir-path='/libabigail-1.8/build/src'
               language='LANG_C_plus_plus'>

    TODO: we can map numbers to languages here.
    """
    dmeta = {
        "_type": "abi-instr",
        "version": __version__,
        # Multiply by 8 to go from bytes to bits
        "address-size": die.cu.header["address_size"] * 8,
        "path": bytes2str(die.attributes["DW_AT_name"].value),
        "language": die.attributes["DW_AT_language"].value,
        "comp-dir-path": bytes2str(die.attributes["DW_AT_comp_dir"].value),
    }
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_namespace(die):
    """parse a DW_TAG_namespace, optionally with children.
    DW_AT_export_symbols indicates that the symbols defined within the
    current scope are to be exported into the enclosing scope.

    TODO: Is DW_AT_export_symbols used anywhere? Where do we get visibility?
    """
    filepath = get_die_filepath(die)

    dmeta = {
        "_type": "namespace",
        "filepath": filepath,
    }

    # These values are not present in all namespace DIEs
    if "DW_AT_name" in die.attributes:
        dmeta["name"] = bytes2str(die.attributes["DW_AT_name"].value)
    if "DW_AT_decl_line" in die.attributes:
        dmeta["line"] = die.attributes["DW_AT_decl_line"].value
    if "DW_AT_decl_column" in die.attributes:
        dmeta["column"] = die.attributes["DW_AT_decl_column"].value

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_subprogram(die):
    """
    <function-decl name='move&lt;abigail::regex::regex_t_deleter&amp;&gt;'
       mangled-name='_ZSt4moveIRN7abigail5regex15regex_t_deleterEEONSt16remove_referenceIT_E4typeEOS5_'
       filepath='/usr/include/c++/9/bits/move.h' line='99' column='1'
       visibility='default' binding='global' size-in-bits='64'>

    TODO: not sure how to derive visibility.
    """
    filepath = get_die_filepath(die)

    dmeta = {"_type": "function-decl"}

    if "DW_AT_name" in die.attributes:
        dmeta["name"] = bytes2str(die.attributes["DW_AT_name"].value)
    if "DW_AT_linkage_name" in die.attributes:
        dmeta["mangled-name"] = bytes2str(die.attributes["DW_AT_linkage_name"].value)
    if filepath:
        dmeta["filepath"] = filepath
    if "DW_AT_decl_line" in die.attributes:
        dmeta["line"] = die.attributes["DW_AT_decl_line"].value
    if "DW_AT_decl_column" in die.attributes:
        dmeta["column"] = die.attributes["DW_AT_decl_column"].value

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_variable(die):
    """
    DIE DW_TAG_variable, size=14, has_children=False
    |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'piecewise_construct', raw_value=16352, offset=8228)
    |DW_AT_decl_file   :  AttributeValue(name='DW_AT_decl_file', form='DW_FORM_data1', value=16, raw_value=16, offset=8232)
    |DW_AT_decl_line   :  AttributeValue(name='DW_AT_decl_line', form='DW_FORM_data1', value=79, raw_value=79, offset=8233)
    |DW_AT_decl_column :  AttributeValue(name='DW_AT_decl_column', form='DW_FORM_data1', value=53, raw_value=53, offset=8234)
    |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=8222, raw_value=8222, offset=8235)
    |DW_AT_declaration :  AttributeValue(name='DW_AT_declaration', form='DW_FORM_flag_present', value=True, raw_value=b'', offset=8239)
    |DW_AT_const_value :  AttributeValue(name='DW_AT_const_value', form='DW_FORM_block1', value=[0], raw_value=[0], offset=8239)
    |DW_AT_const_expr  :  AttributeValue(name='DW_AT_const_expr', form='DW_FORM_flag_present', value=True, raw_value=b'', offset=8241)

    """
    return {}


def parse_typedef(die):
    """parse a DW_TAG_typedef. An example xml is the following:
    <typedef-decl name='value_type' type-id='type-id-5'
                  filepath='/usr/include/c++/9/type_traits'
                  line='60' column='1' id='type-id-4987'/>
    We use the DW_AT_file number to look up the filename in the CompileUnit
    lineprogram for the CU.
    """
    index = die.attributes["DW_AT_decl_file"].value
    filepath = get_cu_filename(die.cu, index)
    return {
        "_type": "typedef-decl",
        "name": bytes2str(die.attributes["DW_AT_name"].value),
        "line": die.attributes["DW_AT_decl_line"].value,
        "column": die.attributes["DW_AT_decl_column"].value,
        "filepath": filepath,
    }


def parse_union_type(die):
    """parse a union type
    <union-decl name='__anonymous_union__' size-in-bits='64'
      is-anonymous='yes' visibility='default'
      filepath='/libabigail-1.8/build/../include/abg-ir.h'
      line='2316' column='1' id='type-id-2748'>
    """
    index = die.attributes["DW_AT_decl_file"].value
    filepath = get_cu_filename(die.cu, index)

    dmeta = {
        "_type": "union-decl",
        "line": die.attributes["DW_AT_decl_line"].value,
        "column": die.attributes["DW_AT_decl_column"].value,
        "filepath": filepath,
        "size-in-bits": die.attributes["DW_AT_byte_size"].value * 8,
        "is-anonymous": "",  # TODO: how do I know if it's anonymous?
        "visibility": "",  # TODO: visibility?,
        "children": [],
    }
    if "DW_AT_name" in die.attributes:
        dmeta["name"] = bytes2str(die.attributes["DW_AT_name"].value)

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_base_type(die):
    """parse a DW_TAG_base_type. Here is the xml equivalent"

    # <type-decl name='__float128' size-in-bits='128' id='type-id-32691'/>
    """
    return {
        "_type": "type-decl",
        "name": bytes2str(die.attributes["DW_AT_name"].value),
        # Size in in bytes, multiply by 8 to get bits
        "size-in-bits": die.attributes["DW_AT_byte_size"].value * 8,
    }


def parse_class_type(die):
    """parse a DW_TAG_class_type. An example XML is the following:

    # <class-decl name='filter_base' size-in-bits='192' is-struct='yes'
                  visibility='default'
                  filepath='/libabigail-1.8/build/../include/abg-comp-filter.h'
                  line='120' column='1' id='type-id-1'>

    TODO: It's not clear how to get visibility "default" here as shown above
    """
    filepath = get_die_filepath(die)

    dmeta = {
        "_type": "class-decl",
        "name": bytes2str(die.attributes["DW_AT_name"].value),
        "is-struct": False,
    }

    # These values are not present in all class declaration DIEs
    if "DW_AT_decl_line" in die.attributes:
        dmeta["line"] = die.attributes["DW_AT_decl_line"].value
    if "DW_AT_decl_column" in die.attributes:
        dmeta["column"] = die.attributes["DW_AT_decl_column"].value
    if "DW_AT_byte_size" in die.attributes:
        dmeta["size-in-bits"] = (die.attributes["DW_AT_byte_size"].value * 8,)

    if filepath:
        dmeta["filepath"] = filepath

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_structure_type(die):
    """DW_TAG_structure, example xml:

    <class-decl name='filter_base' size-in-bits='192' is-struct='yes'
                visibility='default'
                filepath='/libabigail-1.8/build/../include/abg-comp-filter.h'
                line='120' column='1' id='type-id-1'>

    I've changed the "yes" and "no" to be True and False booleans.
    TODO: also not sure how to derive visibility here.
    """
    filepath = get_die_filepath(die)
    dmeta = {
        "_type": "class-decl",
        "is-struct": True,
    }

    # These values are not present in all structure types
    if "DW_AT_name" in die.attributes:
        dmeta["name"] = bytes2str(die.attributes["DW_AT_name"].value)
    if "DW_AT_decl_line" in die.attributes:
        dmeta["line"] = die.attributes["DW_AT_decl_line"].value
    if "DW_AT_decl_column" in die.attributes:
        dmeta["column"] = die.attributes["DW_AT_decl_column"].value
    if "DW_AT_byte_size" in die.attributes:
        dmeta["size-in-bits"] = (die.attributes["DW_AT_byte_size"].value * 8,)

    if filepath:
        dmeta["filepath"] = filepath
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_member(die):
    """DW_TAG_member seems to be nested as follows:

    <data-member access='private' layout-offset-in-bits='0'>
    <var-decl name='_M_ptr' type-id='type-id-202' visibility='default'
        filepath='/usr/include/c++/9/bits/shared_ptr_base.h' line='1404' column='1'/>
    </data-member>

    TODO: where is visibility?
    """
    child = {"_type": "var-decl"}

    filepath = get_die_filepath(die)
    if filepath:
        child["filepath"] = filepath

    # These values are not present in all namespace DIEs
    if "DW_AT_decl_line" in die.attributes:
        child["line"] = die.attributes["DW_AT_decl_line"].value
    if "DW_AT_decl_column" in die.attributes:
        child["column"] = die.attributes["DW_AT_decl_column"].value

    if "DW_AT_name" in die.attributes:
        child["name"] = bytes2str(die.attributes["DW_AT_name"].value)
    return {"_type": "member", "children": [child]}


def parse_parameter(die):
    """parse a DW_TAG_parameter, example xml is:
    <parameter type-id='type-id-28' is-artificial='yes'/>
    """
    artificial = False
    if hasattr(die.attributes, "DW_AT_artificial"):
        artificial = die.attributes["DW_AT_artificial"].value
    return {"_type": "parameter", "is-artificial": artificial}


def parse_inheritance(die):
    # Not sure what this gets parsed into
    # OrderedDict([('DW_AT_type',
    # AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=8855, raw_value=8855, offset=774)),
    # ('DW_AT_data_member_location',
    # AttributeValue(name='DW_AT_data_member_location', form='DW_FORM_data1', value=0, raw_value=0, offset=778))])
    return {}


def parse_enumeration_type(die):
    """parse an enumeration type. The xml looks like this:

    <enum-decl name='_Rb_tree_color' filepath='/usr/include/c++/9/bits/stl_tree.h'
      line='99' column='1' id='type-id-21300'>
      <underlying-type type-id='type-id-297'/>
      <enumerator name='_S_red' value='0'/>
      <enumerator name='_S_black' value='1'/>
    </enum-decl>
    """
    index = die.attributes["DW_AT_decl_file"].value
    filepath = get_cu_filename(die.cu, index)

    dmeta = {
        "_type": "enum-decl",
        "filepath": filepath,
        "line": die.attributes["DW_AT_decl_line"].value,
        "column": die.attributes["DW_AT_decl_column"].value,
    }

    if "DW_AT_name" in die.attributes:
        dmeta["name"] = bytes2str(die.attributes["DW_AT_name"].value)

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_array_type(die):
    """parse an array type. Example XML is:

    <array-type-def dimensions='1' type-id='type-id-444' size-in-bits='64' id='type-id-16411'>
      <subrange length='2' type-id='type-id-1073' id='type-id-20406'/>
    </array-type-def>
    """
    dmeta = {"_type": "array-type-def"}

    if "DW_AT_byte_size" in die.attributes:
        dmeta["size-in-bits"] = (die.attributes["DW_AT_byte_size"].value * 8,)

    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_enumerator(die):
    """parse an enumerator, cild of an enum-dec. Looks like:
    <enumerator name='_S_red' value='0'/>
    <enumerator name='_S_black' value='1'/>
    """
    return {
        "_type": "enumerator",
        "name": die.attributes["DW_AT_name"].value,
        "value": die.attributes["DW_AT_const_value"].value,
    }


def parse_template_type_param(die):
    """parse a template type param. I'm not sure what this gets parsed into,
    looks like:

    DIE DW_TAG_template_type_param, size=9, has_children=False
    |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'_CharT', raw_value=2788, offset=7425)
    |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=375, raw_value=375, offset=7429)
    """
    return {}


def parse_template_value_param(die):
    """parse a template value param. I'm not sure what this gets parsed into,
    looks like:

    DIE DW_TAG_template_value_param, size=10, has_children=False
    |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_string', value=b'__v', raw_value=b'__v', offset=7884)
    |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=19248, raw_value=19248, offset=7888)
    |DW_AT_const_value :  AttributeValue(name='DW_AT_const_value', form='DW_FORM_data1', value=0, raw_value=0, offset=7892)
    """
    return {}


def parse_subrange_type(die):
    """I'm not sure if we need to do additional parsing of the upper bound?

    <subrange length='2' type-id='type-id-1073' id='type-id-20406'/>
    """
    dmeta = {"_type": "subrange"}
    if "DW_AT_upper_bound" in die.attributes:
        dmeta["length"] = die.attributes["DW_AT_upper_bound"].value
    return dmeta


def parse_imported_module(die):
    """I'm not sure what this gets parsed into, looks like:

    DIE DW_TAG_imported_module, size=9, has_children=False
    |DW_AT_decl_file   :  AttributeValue(name='DW_AT_decl_file', form='DW_FORM_data1', value=15, raw_value=15, offset=7459)
    |DW_AT_decl_line   :  AttributeValue(name='DW_AT_decl_line', form='DW_FORM_data2', value=276, raw_value=276, offset=7460)
    |DW_AT_decl_column :  AttributeValue(name='DW_AT_decl_column', form='DW_FORM_data1', value=65, raw_value=65, offset=7462)
    |DW_AT_import      :  AttributeValue(name='DW_AT_import', form='DW_FORM_ref4', value=734, raw_value=734, offset=7463)
    """
    return {}


def parse_inlined_subroutine(die):
    """Not sure what this goes into, maybe a function?
    DIE DW_TAG_inlined_subroutine, size=34, has_children=True
    |DW_AT_abstract_origin:  AttributeValue(name='DW_AT_abstract_origin', form='DW_FORM_ref4', value=25014, raw_value=25014, offset=24772)
    |DW_AT_entry_pc    :  AttributeValue(name='DW_AT_entry_pc', form='DW_FORM_addr', value=1111092, raw_value=1111092, offset=24776)
    |8504              :  AttributeValue(name=8504, form='DW_FORM_data1', value=0, raw_value=0, offset=24784)
    |DW_AT_low_pc      :  AttributeValue(name='DW_AT_low_pc', form='DW_FORM_addr', value=1111092, raw_value=1111092, offset=24785)
    |DW_AT_high_pc     :  AttributeValue(name='DW_AT_high_pc', form='DW_FORM_data8', value=10, raw_value=10, offset=24793)
    |DW_AT_call_file   :  AttributeValue(name='DW_AT_call_file', form='DW_FORM_data1', value=1, raw_value=1, offset=24801)
    |DW_AT_call_line   :  AttributeValue(name='DW_AT_call_line', form='DW_FORM_data2', value=381, raw_value=381, offset=24802)
    |DW_AT_call_column :  AttributeValue(name='DW_AT_call_column', form='DW_FORM_data1', value=9, raw_value=9, offset=24804)
    """
    if die.has_children:
        return {"_type": "inlined-subroutine", "children": []}
    return {"_type": "inlined-subroutine"}


def parse_subroutine_type(die):
    """Not sure what a subroutine type is

    DIE DW_TAG_subroutine_type, size=9, has_children=True
    |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=153, raw_value=153, offset=18354)
    |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=18373, raw_value=18373, offset=18358)
    """
    dmeta = {"_type": "subroutine-type"}
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_imported_declaration(die):
    """I'm not sure what this gets parsed into, looks like:
    DIE DW_TAG_imported_declaration, size=8, has_children=False
    |DW_AT_decl_file   :  AttributeValue(name='DW_AT_decl_file', form='DW_FORM_data1', value=11, raw_value=11, offset=7468)
    |DW_AT_decl_line   :  AttributeValue(name='DW_AT_decl_line', form='DW_FORM_data1', value=127, raw_value=127, offset=7469)
    |DW_AT_decl_column :  AttributeValue(name='DW_AT_decl_column', form='DW_FORM_data1', value=11, raw_value=11, offset=7470)
    |DW_AT_import      :  AttributeValue(name='DW_AT_import', form='DW_FORM_ref4', value=18177, raw_value=18177, offset=7471)
    """
    return {}


def parse_unspecified_type(die):
    """Also not sure what this gets parsed into
    DIE DW_TAG_unspecified_type, size=6, has_children=False
    |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'decltype(nullptr)', raw_value=12681, offset=19244)
    """
    return {}


def parse_reference_type(die):
    """parse a reference type, xml looks like:
    <reference-type-def kind='lvalue' type-id='type-id-20945' size-in-bits='64' id='type-id-20052'/>

    # TODO: where do we get kind? DW_AT_type? Is this an lvalue?
    """
    return {
        "_type": "reference-type-def",
        "size-in-bits": die.attributes["DW_AT_byte_size"].value * 8,
        "type": "lvalue",
    }


def parse_rvalue_reference_type(die):
    return {
        "_type": "reference-type-def",
        "size-in-bits": die.attributes["DW_AT_byte_size"].value * 8,
        "kind": "rvalue",
    }


def parse_volatile_type(die):
    """Not sure what this gets parsed into
    DIE DW_TAG_volatile_type, size=6, has_children=False
    |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=22671, raw_value=22671, offset=22685)
    """
    return {}


def parse_template_parameter_pack(die):
    """not sure what this goes into
    DIE DW_TAG_GNU_template_parameter_pack, size=9, has_children=True
    |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'_Args', raw_value=1841328, offset=39845)
    |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=11585, raw_value=11585, offset=39849)
    """
    dmeta = {"_type": "template-parameter-pack"}
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_gnu_call_site(die):
    """Not sure what this is
    DIE DW_TAG_GNU_call_site, size=13, has_children=True
    |DW_AT_low_pc      :  AttributeValue(name='DW_AT_low_pc', form='DW_FORM_addr', value=1111102, raw_value=1111102, offset=24919)
    |DW_AT_GNU_tail_call:  AttributeValue(name='DW_AT_GNU_tail_call', form='DW_FORM_flag_present', value=True, raw_value=b'', offset=24927)
    |DW_AT_abstract_origin:  AttributeValue(name='DW_AT_abstract_origin', form='DW_FORM_ref4', value=28213, raw_value=28213, offset=24927)
    """
    dmeta = {"_type": "gnu-call-site"}
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_lexical_block(die):
    """Not sure where this goes!"""
    dmeta = {"_type": "lexical-block"}
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_gnu_call_site_parameter(die):
    """
    DIE DW_TAG_GNU_call_site_parameter, size=7, has_children=False
    |DW_AT_location    :  AttributeValue(name='DW_AT_location', form='DW_FORM_exprloc', value=[85], raw_value=[85], offset=24932)
    |DW_AT_GNU_call_site_value:  AttributeValue(name='DW_AT_GNU_call_site_value', form='DW_FORM_exprloc', value=[243, 1, 85], raw_value=[243, 1, 85], offset=24934)
    """
    dmeta = {"_type": "gnu-call-site-parameter"}
    if die.has_children:
        dmeta["children"] = []
    return dmeta


def parse_children(die, parent=None, child_list=None):
    """parse children will loop recursively through dwarf information entries
    and based on the type, add it to the list of children. We then parse
    any remaining children.
    """
    dmeta = {}

    if die.tag == "DW_TAG_compile_unit":
        dmeta = parse_compile_unit(die)

    elif die.tag == "DW_TAG_namespace":
        dmeta = parse_namespace(die)

    elif die.tag == "DW_TAG_subprogram":
        dmeta = parse_subprogram(die)

    elif die.tag == "DW_TAG_variable":
        dmeta = parse_variable(die)

    elif die.tag == "DW_TAG_typedef":
        dmeta = parse_typedef(die)

    elif die.tag == "DW_TAG_union_type":
        dmeta = parse_union_type(die)

    # <pointer-type-def type-id='type-id-7365' size-in-bits='64' id='type-id-9196'/>
    elif die.tag == "DW_TAG_pointer_type":
        dmeta = {
            "_type": "pointer-type-def",
            "size-in-bits": die.attributes["DW_AT_byte_size"].value * 8,
        }

    # <qualified-type-def type-id='type-id-37873' const='yes' id='type-id-37880'/>
    elif die.tag == "DW_TAG_const_type":
        dmeta = {"_type": "qualified-type-def", "const": "yes"}

    elif die.tag == "DW_TAG_base_type":
        dmeta = parse_base_type(die)

    elif die.tag == "DW_TAG_class_type":
        dmeta = parse_class_type(die)

    elif die.tag == "DW_TAG_structure_type":
        dmeta = parse_structure_type(die)

    elif die.tag == "DW_TAG_formal_parameter":
        dmeta = parse_parameter(die)

    elif die.tag == "DW_TAG_member":
        dmeta = parse_member(die)

    elif die.tag == "DW_TAG_inheritance":
        dmeta = parse_inheritance(die)

    elif die.tag == "DW_TAG_template_type_param":
        dmeta = parse_template_type_param(die)

    elif die.tag == "DW_TAG_template_value_param":
        dmeta = parse_template_value_param(die)

    elif die.tag == "DW_TAG_imported_module":
        dmeta = parse_imported_module(die)

    elif die.tag == "DW_TAG_imported_declaration":
        dmeta = parse_imported_declaration(die)

    elif die.tag == "DW_TAG_enumeration_type":
        dmeta = parse_enumeration_type(die)

    elif die.tag == "DW_TAG_array_type":
        dmeta = parse_array_type(die)

    elif die.tag == "DW_TAG_subrange_type":
        dmeta = parse_subrange_type(die)

    elif die.tag == "DW_TAG_subroutine_type":
        dmeta = parse_subroutine_type(die)

    elif die.tag == "DW_TAG_inlined_subroutine":
        dmeta = parse_inlined_subroutine(die)

    elif die.tag == "DW_TAG_enumerator":
        dmeta = parse_enumerator(die)

    elif die.tag == "DW_TAG_unspecified_type":
        dmeta = parse_unspecified_type(die)

    elif die.tag == "DW_TAG_reference_type":
        dmeta = parse_reference_type(die)

    elif die.tag == "DW_TAG_rvalue_reference_type":
        dmeta = parse_rvalue_reference_type(die)

    elif die.tag == "DW_TAG_GNU_call_site":
        dmeta = parse_gnu_call_site(die)

    elif die.tag == "DW_TAG_GNU_call_site_parameter":
        dmeta = parse_gnu_call_site_parameter(die)

    # I don't see any attributes here
    elif die.tag == "DW_TAG_unspecified_parameters":
        dmeta = {}

    elif die.tag == "DW_TAG_GNU_template_parameter_pack":
        dmeta = parse_template_parameter_pack(die)

    elif die.tag == "DW_TAG_volatile_type":
        dmeta = parse_volatile_type(die)

    elif die.tag == None:
        dmeta = {}

    elif die.tag == "DW_TAG_lexical_block":
        dmeta = parse_lexical_block(die)

    else:
        print("%s not parsed." % die.tag)

    # We keep a handle on the root to return
    if not parent:
        parent = dmeta
    elif dmeta:
        child_list.append(dmeta)

    if die.has_children:
        for child in die.iter_children():
            parse_children(child, parent, dmeta["children"])
    return parent


def attribute_has_location_list(attr):
    """Only some attributes can have location list values, if they have the
    required DW_FORM (loclistptr "class" in DWARF spec v3)
    """
    if attr.name in (
        "DW_AT_location",
        "DW_AT_string_length",
        "DW_AT_const_value",
        "DW_AT_return_addr",
        "DW_AT_data_member_location",
        "DW_AT_frame_base",
        "DW_AT_segment",
        "DW_AT_static_link",
        "DW_AT_use_location",
        "DW_AT_vtable_elem_location",
    ):
        if attr.form in ("DW_FORM_data4", "DW_FORM_data8"):
            return True
    return False
