# This is based on asp.py from spack/spack, copyright LLNL and spack developers
# It will eventually be added back to that scope - this script is developing
# new functionality to work with ABI.

import collections
import copy
import hashlib
import itertools
import os
import pprint
import re
import sys
import time
import types

# Since we parse the die's directly, we use these pyelftools supporting functions.
from elftools.common.py3compat import bytes2str
from elftools.dwarf.descriptions import describe_attr_value
from elftools.elf.descriptions import (
    describe_symbol_type,
    describe_symbol_bind,
    describe_symbol_visibility,
    describe_symbol_shndx,
)

from six import string_types

# An arbitrary version for this asp.py (libabigail has one, so we are copying)
__version__ = "1.0.0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import clingo
    from corpus import ABIParser

    # There may be a better way to detect this
    clingo_cffi = hasattr(clingo.Symbol, "_rep")
except ImportError:
    sys.exit("clingo for Python and the corpus.py file are required.")


if sys.version_info >= (3, 3):
    from collections.abc import Sequence  # novm
else:
    from collections import Sequence


class Timer(object):
    """Simple timer for timing phases of a solve"""

    def __init__(self):
        self.start = time.time()
        self.last = self.start
        self.phases = {}

    def phase(self, name):
        last = self.last
        now = time.time()
        self.phases[name] = now - last
        self.last = now

    def write(self, out=sys.stdout):
        now = time.time()
        out.write("Time:\n")
        for phase, t in self.phases.items():
            out.write("    %-15s%.4f\n" % (phase + ":", t))
        out.write("Total: %.4f\n" % (now - self.start))


def issequence(obj):
    if isinstance(obj, string_types):
        return False
    return isinstance(obj, (Sequence, types.GeneratorType))


def listify(args):
    if len(args) == 1 and issequence(args[0]):
        return list(args[0])
    return list(args)


class AspObject(object):
    """Object representing a piece of ASP code."""


def _id(thing):
    """Quote string if needed for it to be a valid identifier."""
    if isinstance(thing, AspObject):
        return thing
    elif isinstance(thing, bool):
        return '"%s"' % str(thing)
    elif isinstance(thing, int):
        return str(thing)
    else:
        return '"%s"' % str(thing)


class AspFunction(AspObject):
    def __init__(self, name, args=None):
        self.name = name
        self.args = [] if args is None else args

    def __call__(self, *args):
        return AspFunction(self.name, args)

    def symbol(self, positive=True):
        def argify(arg):
            if isinstance(arg, bool):
                return clingo.String(str(arg))
            elif isinstance(arg, int):
                return clingo.Number(arg)
            else:
                return clingo.String(str(arg))

        return clingo.Function(
            self.name, [argify(arg) for arg in self.args], positive=positive
        )

    def __getitem___(self, *args):
        self.args[:] = args
        return self

    def __str__(self):
        return "%s(%s)" % (self.name, ", ".join(str(_id(arg)) for arg in self.args))

    def __repr__(self):
        return str(self)


class AspFunctionBuilder(object):
    def __getattr__(self, name):
        return AspFunction(name)


fn = AspFunctionBuilder()


class Result(object):
    """Result of an ASP solve."""

    def __init__(self, asp=None):
        self.asp = asp
        self.satisfiable = None
        self.optimal = None
        self.warnings = None
        self.nmodels = 0

        # specs ordered by optimization level
        self.answers = []
        self.cores = []

    def print_cores(self):
        for core in self.cores:
            tty.msg(
                "The following constraints are unsatisfiable:",
                *sorted(str(symbol) for symbol in core)
            )


class PyclingoDriver(object):
    def __init__(self, cores=True, asp=None):
        """Driver for the Python clingo interface.

        Arguments:
            cores (bool): whether to generate unsatisfiable cores for better
                error reporting.
            asp (file-like): optional stream to write a text-based ASP program
                for debugging or verification.
        """
        global clingo
        self.out = asp or sys.stdout  # self.devnull
        self.cores = cores

    def devnull(self):
        self.f = open(os.devnull, "w")
        self.out = f

    def __exit__(self):
        self.f.close()

    def title(self, name, char):
        self.out.write("\n")
        self.out.write("%" + (char * 76))
        self.out.write("\n")
        self.out.write("%% %s\n" % name)
        self.out.write("%" + (char * 76))
        self.out.write("\n")

    def h1(self, name):
        self.title(name, "=")

    def h2(self, name):
        self.title(name, "-")

    def newline(self):
        self.out.write("\n")

    def fact(self, head):
        """ASP fact (a rule without a body)."""
        symbol = head.symbol() if hasattr(head, "symbol") else head

        self.out.write("%s.\n" % str(symbol))

        atom = self.backend.add_atom(symbol)
        self.backend.add_rule([atom], [], choice=self.cores)
        if self.cores:
            self.assumptions.append(atom)

    def solve(
        self,
        solver_setup,
        corpora,
        dump=None,
        nmodels=0,
        timers=False,
        stats=False,
        tests=False,
        logic_programs=None,
        facts_only=False,
    ):
        """Given three corpora, generate facts for a solver.

        The order is important:

         [binary, libraryA, libraryB]:
           binary: should be a binary that uses libraryA
           libraryA: should be a known library to work with the binary
           libraryB: should be a second library to test if it will work.

        In the future ideally we would not want to require this working library,
        but for now we are trying to emulate what libabigail does. The first
        working binary serves as a base to subset the symbols to a known set
        that are needed. We could possibly remove it if we can load all symbols
        provided by other needed files, and then eliminate them from the set.
        """
        # logic programs to give to the solver
        logic_programs = logic_programs or []
        if not isinstance(logic_programs, list):
            logic_programs = [logic_programs]

        timer = Timer()

        # Initialize the control object for the solver
        self.control = clingo.Control()
        self.control.configuration.solve.models = nmodels
        self.control.configuration.asp.trans_ext = "all"
        self.control.configuration.asp.eq = "5"
        self.control.configuration.configuration = "tweety"
        self.control.configuration.solve.parallel_mode = "2"
        self.control.configuration.solver.opt_strategy = "usc,one"

        # set up the problem -- this generates facts and rules
        self.assumptions = []
        with self.control.backend() as backend:
            self.backend = backend
            solver_setup.setup(self, corpora, tests=tests)
        timer.phase("setup")

        # If we only want to generate facts, cut out early
        if facts_only:
            return

        # read in the main ASP program and display logic -- these are
        # handwritten, not generated, so we load them as resources
        parent_dir = os.path.dirname(__file__)
        for logic_program in logic_programs:
            self.control.load(os.path.join(parent_dir, logic_program))
        timer.phase("load")

        # Grounding is the first step in the solve -- it turns our facts
        # and first-order logic rules into propositional logic.
        self.control.ground([("base", [])])
        timer.phase("ground")

        # With a grounded program, we can run the solve.
        result = Result()
        models = []  # stable models if things go well
        cores = []  # unsatisfiable cores if they do not

        def on_model(model):
            models.append((model.cost, model.symbols(shown=True, terms=True)))

        # Won't work after this, need to write files
        solve_kwargs = {
            #    "assumptions": self.assumptions,
            "on_model": on_model,
            #     "on_core": cores.append,
        }
        # if clingo_cffi:
        #    solve_kwargs["on_unsat"] = cores.append
        solve_result = self.control.solve(**solve_kwargs)
        timer.phase("solve")

        # This part isn't developed yet
        import IPython

        IPython.embed()

        # once done, construct the solve result
        # result.satisfiable = solve_result.satisfiable

        # def stringify(x):
        #    if clingo_cffi:
        #        # Clingo w/ CFFI will throw an exception on failure
        #        try:
        #            return x.string
        #        except RuntimeError:
        #            return str(x)
        #    else:
        #        return x.string or str(x)

        # if result.satisfiable:
        #    min_cost, best_model = min(models)
        #    tuples = [
        #        (sym.name, [stringify(a) for a in sym.arguments]) for sym in best_model
        #    ]
        #    result.answers.append((list(min_cost)))

        # elif cores:
        #    symbols = dict((a.literal, a.symbol) for a in self.control.symbolic_atoms)
        #    for core in cores:
        #        core_symbols = []
        #        for atom in core:
        #            sym = symbols[atom]
        #            if sym.name == "rule":
        #                sym = sym.arguments[0].string
        #            core_symbols.append(sym)
        #        result.cores.append(core_symbols)

        if timers:
            timer.write()
            print()
        if stats:
            print("Statistics:")
            pprint.pprint(self.control.statistics)

        return result


class ABICompatSolverSetup(object):
    """Class to set up and run an ABI Compatability Solver."""

    def __init__(self):
        self.gen = None  # set by setup()

        # A lookup of DIEs based on corpus path (first key) and id
        # (second key) DIE == Dwarf Information Entry
        self.die_lookup = {}

        # A lookup of DIE children ids
        self.child_lookup = {}
        self.language = None

    def generate_elf_symbols(self, corpora, prefix=""):
        """For each corpus, write out elf symbols as facts. Note that we are
        trying a more detailed approach with facts/atoms being named (e.g.,
        symbol_type instead of symbol_attr). We could also try a simpler
        approach:

        symbol_type("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STT_FUNC").
        symbol_binding("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STB_FUNC").
        symbol_attr("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STV_default").

        """
        # If we have a prefix, add a spacer
        prefix = "%s_" % prefix if prefix else ""

        for corpus in corpora:
            self.gen.h2("Corpus symbols: %s" % corpus.path)

            for symbol, meta in corpus.elfsymbols.items():

                # It begins with a NULL symbol, not sure it's useful
                if not symbol:
                    continue

                self.gen.fact(AspFunction(prefix + "symbol", args=[symbol]))
                self.gen.fact(
                    AspFunction(
                        prefix + "symbol_type", args=[corpus.path, symbol, meta["type"]]
                    )
                )
                self.gen.fact(
                    AspFunction(
                        prefix + "symbol_version",
                        args=[corpus.path, symbol, meta["version_info"]],
                    )
                )
                self.gen.fact(
                    AspFunction(
                        prefix + "symbol_binding",
                        args=[corpus.path, symbol, meta["binding"]],
                    )
                )
                self.gen.fact(
                    AspFunction(
                        prefix + "symbol_visibility",
                        args=[corpus.path, symbol, meta["visibility"]],
                    )
                )
                self.gen.fact(
                    AspFunction(
                        prefix + "symbol_definition",
                        args=[corpus.path, symbol, meta["defined"]],
                    )
                )

                # Might be redundant
                has = "has_%s" % prefix if prefix else "has_"
                self.gen.fact(AspFunction(has + "symbol", args=[corpus.path, symbol]))
                self.gen.fact(fn.has_symbol(corpus.path, symbol))

    def _die_hash(self, die, corpus, parent):
        """
        We need a unique id for a die entry based on it's corpus, cu, content
        """
        hasher = hashlib.md5()
        hasher.update(str(die).encode("utf-8"))
        hasher.update(corpus.path.encode("utf-8"))
        hasher.update(str(die.cu.cu_offset).encode('utf-8'))
        if parent:
            hasher.update(parent.encode("utf-8"))
        return hasher.hexdigest()

    def generate_needed(self, corpora):
        """
        Given a list of corpora, add needed libraries from dynamic tags.
        """
        for corpus in corpora:
            for needed in corpus.dynamic_tags.get("needed", []):
                self.gen.fact(fn.corpus_needs_library(corpus.path, needed))

    def generate_dwarf_information_entries(self, corpora, prefix=""):
        """
        Given a list of corpora, add needed libraries from dynamic tags.

        For needed corpus attributes, we add a prefix.
        """

        # We will keep a lookup of die
        for corpus in corpora:
            self.gen.h2("Corpus DIE: %s" % corpus.path)

            # Add to child and die lookup, for redundancy check
            if corpus.path not in self.die_lookup:
                self.die_lookup[corpus.path] = {}
            if corpus.path not in self.child_lookup:
                self.child_lookup[corpus.path] = {}

            for die in corpus.iter_dwarf_information_entries():

                # Skip entries without tags
                if not die.tag:
                    continue

                # Parse the die entry!
                self._parse_die_children(corpus, die, prefix=prefix)

    def _add_children(self, corpus, die, prefix=None):
        """
        Add children ids to the lookup, ensuring we print the relationship
        only once.
        """

        def uid(corpus, die):
            return "%s_%s" % (corpus.path, die.abbrev_code)

        lookup = self.child_lookup[corpus.path]

        # Add the child lookup
        if die.unique_id not in lookup:
            lookup[die.unique_id] = set()

        # If we have a prefix, add a _
        if prefix and not prefix.endswith('_'):
            prefix = "%s_" % prefix

        # If it's a DW_TAG_subprogram, keep track of child parameter order
        # We add one each time, so count starts at 0 after that
        parameter_count = -1
        for child in die.iter_children():
            child_id = self._die_hash(child, corpus, die.unique_id)
            if child_id in lookup[die.unique_id]:
                continue
            lookup[die.unique_id].add(child_id)

            # If it's a subprogram, we care about order of parameters
            if die.tag == "DW_TAG_subprogram" and child.tag == "DW_TAG_formal_parameter":
                parameter_count +=1 
                self.gen.fact(
                    AspFunction(prefix + "dw_tag_formal_parameter_order", args=[corpus.path, child_id, parameter_count])
                )

            self.gen.fact(fn.die_has_child(die.unique_id, child_id))

    def _get_tag(self, die, prefix):
        """Get a clingo appropriate tag name.
        
        The die tag needs to be parsed to be all lowercase, and for some 
        die tags, we want to remove the "Dwarf specific words." (e.g.,
        a subprogram --> a function
        """
        tag = die.tag.lower()

        # A subprogram is a function
        if "subprogram" in tag:
            tag = re.sub('subprogram', 'function', tag)

        # Special cases of
        if prefix:
            tag = "%s_%s" % (prefix.lower(), tag)
        return tag

    def _parse_die_children(self, corpus, die, parent=None, prefix=""):
        """
        Parse die children, writing facts for attributions and relationships.

        Parse die children will loop recursively through dwarf information
        entries, and based on the type, generate facts for it, ensuring that
        we also create facts that represent relationships. For each, we generate:

        - atoms about the die id itself, in lowercase for clingo
        - atoms about having children (die_has_child)
        - atoms about attributes, in the form <tag>_language(corpus, id, value)

        Each die has a unique id scoped within the corpus, so we provide the
        corpus along with the id and the value of the attribute. I've provided
        separate functions less so for good structure, but moreso so that I
        can write notes alongside each. Some functions have notes and just pass.

        TODO: read through http://dwarfstd.org/doc/dwarf_1_1_0.pdf for each type
        and make sure not missing anything. Tags are on page 28.
        """
        # Get the tag for the die
        tag = self._get_tag(die, prefix)

        # Keep track of unique id for relationships (hash of attributes, parent, and corpus)
        die.unique_id = self._die_hash(die, corpus, parent)

        # Don't parse an entry twice
        # if die.abbrev_code in self.die_lookup[corpus.path]:
        #    return

        # Create a top level entry for the die based on it's tag type
        self.gen.fact(AspFunction(tag, args=[corpus.path, die.unique_id]))

        # Children are represented as facts
        self._add_children(corpus, die, prefix)

        # Add to the lookup
        self.die_lookup[corpus.path][die.abbrev_code] = die

        # Parse common attributes
        self._parse_common_attributes(corpus, die, tag)

        if die.tag == "DW_TAG_compile_unit":
            self._parse_compile_unit(corpus, die, tag)

        elif die.tag == "DW_TAG_namespace":
            self._parse_namespace(corpus, die, tag)

        elif die.tag == "DW_TAG_subprogram":
            self._parse_subprogram(corpus, die, tag)

        elif die.tag == "DW_TAG_variable":
            self._parse_variable(corpus, die, tag)

        elif die.tag == "DW_TAG_typedef":
            self._parse_typedef(corpus, die, tag)

        elif die.tag == "DW_TAG_union_type":
            self._parse_union_type(corpus, die, tag)

        elif die.tag == "DW_TAG_pointer_type":
            self._parse_pointer_type(corpus, die, tag)

        elif die.tag == "DW_TAG_const_type":
            self._parse_const_type(corpus, die, tag)

        elif die.tag == "DW_TAG_base_type":
            self._parse_base_type(corpus, die, tag)

        elif die.tag == "DW_TAG_class_type":
            self._parse_class_type(corpus, die, tag)

        elif die.tag == "DW_TAG_structure_type":
            self._parse_structure_type(corpus, die, tag)

        elif die.tag == "DW_TAG_formal_parameter":
            self._parse_parameter(corpus, die, tag)

        elif die.tag == "DW_TAG_member":
            self._parse_member(corpus, die, tag)

        elif die.tag == "DW_TAG_inheritance":
            self._parse_inheritance(corpus, die, tag)

        elif die.tag == "DW_TAG_template_type_param":
            self._parse_template_type_param(corpus, die, tag)

        elif die.tag == "DW_TAG_template_value_param":
            self._parse_template_value_param(corpus, die, tag)

        elif die.tag == "DW_TAG_imported_module":
            self._parse_imported_module(corpus, die, tag)

        elif die.tag == "DW_TAG_imported_declaration":
            self._parse_imported_declaration(corpus, die, tag)

        elif die.tag == "DW_TAG_enumeration_type":
            self._parse_enumeration_type(corpus, die, tag)

        elif die.tag == "DW_TAG_array_type":
            self._parse_array_type(corpus, die, tag)

        elif die.tag == "DW_TAG_subrange_type":
            self._parse_subrange_type(corpus, die, tag)

        elif die.tag == "DW_TAG_subroutine_type":
            self._parse_subroutine_type(corpus, die, tag)

        elif die.tag == "DW_TAG_inlined_subroutine":
            self._parse_inlined_subroutine(corpus, die, tag)

        elif die.tag == "DW_TAG_enumerator":
            self._parse_enumerator(corpus, die, tag)

        elif die.tag == "DW_TAG_unspecified_type":
            self._parse_unspecified_type(corpus, die, tag)

        elif die.tag == "DW_TAG_reference_type":
            self._parse_reference_type(corpus, die, tag)

        elif die.tag == "DW_TAG_rvalue_reference_type":
            self._parse_rvalue_reference_type(corpus, die, tag)

        elif die.tag == "DW_TAG_GNU_call_site":
            self._parse_gnu_call_site(corpus, die, tag)

        elif die.tag == "DW_TAG_GNU_call_site_parameter":
            self._parse_gnu_call_site_parameter(corpus, die, tag)

        # I don't see any attributes here
        elif die.tag == "DW_TAG_unspecified_parameters":
            pass

        elif die.tag == "DW_TAG_GNU_template_parameter_pack":
            self._parse_template_parameter_pack(corpus, die, tag)

        elif die.tag == "DW_TAG_volatile_type":
            self._parse_volatile_type(corpus, die, tag)

        elif die.tag == None:
            pass

        # Haven't seen these yet
        elif die.tag in [
            "DW_TAG_padding",
            "DW_TAG_entry_point",
            "DW_TAG_global_parameter",
            "DW_TAG_global_subroutine",
            "DW_AT_global_variable",
            "DW_TAG_label",
            "DW_TAG_local_variable",
            "DW_TAG_source_file",
            "DW_TAG_string_type",
            "DW_TAG_subroutine",
            "DW_tag_variant",
            "DW_TAG_common_block",
            "DW_TAG_common_inclusion",
            "DW_TAG_ptr_to_member_type",
            "DW_TAG_set_type",
            "DW_TAG_with_stmt",
            "DW_TAG_lo_user",
            "DW_TAG_hi_user",
        ]:
            print("Found tag not yet seen yet, %s" % die.tag)
            import IPython

            IPython.embed()

        elif die.tag == "DW_TAG_lexical_block":
            self._parse_lexical_block(corpus, die, tag)

        else:
            print("%s not parsed." % tag)

        # We keep a handle on the root to return
        if not parent:
            parent = die.unique_id

        if die.has_children:
            for child in die.iter_children():
                self._parse_die_children(corpus, child, parent, prefix)

    def _parse_common_attributes(self, corpus, die, tag):
        """
        Many share these attributes, so we have a common function to parse.
        It's actually easier to just check for an attribute, and parse it
        if it's present, and be sure that we don't miss any.
        """
        if "DW_AT_name" in die.attributes:
            name = bytes2str(die.attributes["DW_AT_name"].value)
            self.gen.fact(
                AspFunction(tag + "_name", args=[corpus.path, die.unique_id, name])
            )

        # DW_AT_type is a reference to another die (the type)
        if "DW_AT_type" in die.attributes:
            self._parse_die_type(corpus, die, tag)

        # Not to be confused with "bite size" :)
        if "DW_AT_byte_size" in die.attributes:
            size_in_bits = die.attributes["DW_AT_byte_size"].value * 8
            self.gen.fact(
                AspFunction(
                    tag + "_size_in_bits",
                    args=[corpus.path, die.unique_id, size_in_bits],
                )
            )

        # Declaration line
        if "DW_AT_decl_line" in die.attributes:
            line = die.attributes["DW_AT_decl_line"].value
            self.gen.fact(
                AspFunction(tag + "_line", args=[corpus.path, die.unique_id, line])
            )

        # Declaration column
        if "DW_AT_decl_column" in die.attributes:
            column = die.attributes["DW_AT_decl_column"].value
            self.gen.fact(
                AspFunction(tag + "_column", args=[corpus.path, die.unique_id, column])
            )

        # The size this DIE occupies in the section (not sure about units)
        if hasattr(die, "size"):
            self.gen.fact(
                AspFunction(
                    tag + "_die_size", args=[corpus.path, die.unique_id, die.size]
                )
            )

        # Some attributes have a filepath
        filepath = _get_die_filepath(die)
        if filepath:
            self.gen.fact(
                AspFunction(
                    tag + "_filepath", args=[corpus.path, die.unique_id, filepath]
                )
            )

        # DW_AT_external: "If the name of the subroutine described by an entry with the tag
        # DW_TAG_subprogram is visible outside of its containing compilation unit, that
        # entry has a DW_AT_external attribute, which is a flag."
        # I think this is visibility? But let's call it external in case not.
        if (
            "DW_AT_external" in die.attributes
            and die.attributes["DW_AT_external"].value == True
        ):
            self.gen.fact(
                AspFunction(tag + "_external", args=[corpus.path, die.unique_id, name])
            )

        # This looks like the "mangled string" for a subprogram. Doesn't hurt to check here
        if "DW_AT_linkage_name" in die.attributes:
            name = bytes2str(die.attributes["DW_AT_linkage_name"].value)
            self.gen.fact(
                AspFunction(
                    tag + "_mangled_name", args=[corpus.path, die.unique_id, name]
                )
            )
        if (
            "DW_AT_explicit" in die.attributes
            and die.attributes["DW_AT_explicit"].value == True
        ):
            self.gen.fact(
                AspFunction(tag + "_explicit", args=[corpus.path, die.unique_id, "yes"])
            )
        if (
            "DW_AT_defaulted" in die.attributes
            and die.attributes["DW_AT_defaulted"].value == True
        ):
            self.gen.fact(
                AspFunction(
                    tag + "_defaulted", args=[corpus.path, die.unique_id, "yes"]
                )
            )

        if "DW_AT_const_value" in die.attributes:
            # This might not easily map to clingo (e.g., [0],) so we make a string
            const_value = str(die.attributes["DW_AT_const_value"].value)
            self.gen.fact(
                AspFunction(
                    tag + "_const_value", args=[corpus.path, die.unique_id, const_value]
                )
            )

        if "DW_AT_const_expr" in die.attributes:
            self.gen.fact(
                AspFunction(
                    tag + "_const_expr", args=[corpus.path, die.unique_id, "yes"]
                )
            )

        # E.g., 7	(unsigned)
        if "DW_AT_encoding" in die.attributes:
            encoding = describe_attr_value(
                die.attributes["DW_AT_encoding"], die, die.offset
            )
            self.gen.fact(
                AspFunction(
                    tag + "_encoding", args=[corpus.path, die.unique_id, encoding]
                )
            )

    def _parse_die_type(self, corpus, die, tag, lookup_die=None):
        """
        Parse the die type, typically getting the size in bytes or
        looking it up. If lookup die is provided, it means we are digging into
        layers and are looking for a type for "die"

        Might be useful:
        https://www.gitmemory.com/issue/eliben/pyelftools/353/784166976

        """
        type_die = None

        # The die we query for the type is either the die itself, or one we've
        # already found
        query_die = lookup_die or die

        # CU relative offset
        if query_die.attributes["DW_AT_type"].form.startswith("DW_FORM_ref"):
            type_die = query_die.cu.get_DIE_from_refaddr(
                query_die.attributes["DW_AT_type"].value
            )

        # Absolute offset
        elif query_die.attributes["DW_AT_type"].startswith("DW_FORM_ref_addr"):
            print("ABSOLUTE OFFSET")
            import IPython

            IPython.embed()

        # If we grabbed the type, just explicitly write the size/type
        # In the future we could reference another die, but don't
        # have it's parent here at the moment
        if type_die:

            # If we have another type def, call function again until we find it
            if "DW_AT_type" in type_die.attributes:
                return self._parse_die_type(corpus, die, tag, type_die)

            # If it's a pointer, we have the byte size (no name)
            if type_die.tag == "DW_TAG_pointer_type":
                size_in_bits = type_die.attributes["DW_AT_byte_size"].value * 8
                self.gen.fact(
                    AspFunction(
                        tag + "_size_in_bits",
                        args=[corpus.path, die.unique_id, size_in_bits],
                    )
                )

            # Not sure how to parse non complete types
            # https://stackoverflow.com/questions/38225269/dwarf-reading-not-complete-types
            elif "DW_AT_declaration" in type_die.attributes:
                self.gen.fact(
                    AspFunction(
                        tag + "_non_complete_type",
                        args=[corpus.path, die.unique_id, "yes"],
                    )
                )

            # Here we are supposed to walk member types and calc size with offsets
            # For now let's assume we can just compare all child sizes
            # https://github.com/eliben/pyelftools/issues/306#issuecomment-606677552
            elif "DW_AT_byte_size" not in type_die.attributes:
                return

            else:
                type_size = type_die.attributes["DW_AT_byte_size"].value * 8
                self.gen.fact(
                    AspFunction(
                        tag + "_size_in_bits",
                        args=[corpus.path, die.unique_id, type_size],
                    )
                )
                type_name = None
                if "DW_AT_linkage_name" in type_die.attributes:
                    type_name = bytes2str(
                        type_die.attributes["DW_AT_linkage_name"].value
                    )
                elif "DW_AT_name" in type_die.attributes:
                    type_name = bytes2str(type_die.attributes["DW_AT_name"].value)

                if type_name:
                    self.gen.fact(
                        AspFunction(
                            tag + "_type_name",
                            args=[corpus.path, die.unique_id, type_name],
                        )
                    )

    def _parse_compile_unit(self, corpus, die, tag):
        """
        Parse a compile unit (usually at the top).

        A compile unit (in xml) looks like the following:

        <abi-instr version='1.0' address-size='64'
                   path='../../src/abg-regex.cc' comp-dir-path='/libabigail-1.8/build/src'
                   language='LANG_C_plus_plus'>

        Note that "path" is called "name" for this parser since it's a common attribute.
        Not included:
          AttributeValue(name='DW_AT_producer', form='DW_FORM_strp', value=b'GNU C++14 9.3.0 -mtune=generic -march=x86-64 -g -fasynchronous-unwind-tables -fstack-protector-strong -fstack-clash-protection -fcf-protection', raw_value=3526, offset=12)
          AttributeValue(name='DW_AT_low_pc', form='DW_FORM_addr', value=4681, raw_value=4681, offset=25)
          AttributeValue(name='DW_AT_high_pc', form='DW_FORM_data8', value=443, raw_value=443, offset=33)
          AttributeValue(name='DW_AT_stmt_list', form='DW_FORM_sec_offset', value=0, raw_value=0, offset=41)
        """
        tag = die.tag.lower()

        # Prepare attributes for facts - keep language
        language = describe_attr_value(
            die.attributes["DW_AT_language"], die, die.offset
        )
        comp_dir_path = bytes2str(die.attributes["DW_AT_comp_dir"].value)
        self.language = language

        # Multiply by 8 to go from bytes to bits
        address_size = die.cu.header["address_size"] * 8

        # The version of this software
        self.gen.fact(
            AspFunction(
                tag + "_asp_version", args=[corpus.path, die.unique_id, __version__]
            )
        )

        # Attributes we expect to see in libabigail
        self.gen.fact(
            AspFunction(
                tag + "_comp_dir_path", args=[corpus.path, die.unique_id, comp_dir_path]
            )
        )
        self.gen.fact(
            AspFunction(
                tag + "_address_size_bits",
                args=[corpus.path, die.unique_id, address_size],
            )
        )
        self.gen.fact(
            AspFunction(tag + "_language", args=[corpus.path, die.unique_id, language])
        )

    def _parse_namespace(self, corpus, die, tag):
        """
        Parse a DW_TAG_namespace.

        DW_AT_export_symbols indicates that the symbols defined within the
        current scope are to be exported into the enclosing scope.

        Not currently included:
        |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=4052, raw_value=4052, offset=52)
        This attribute looks like it's used to find the next CU offset.
        https://github.com/eliben/pyelftools/blob/46187f45f6085c8e28b7878c4058283d3ba5b812/elftools/dwarf/compileunit.py#L156
        """
        pass

    def _parse_subprogram(self, corpus, die, tag):
        """
        <function-decl name='move&lt;abigail::regex::regex_t_deleter&amp;&gt;'
           mangled-name='_ZSt4moveIRN7abigail5regex15regex_t_deleterEEONSt16remove_referenceIT_E4typeEOS5_'
           filepath='/usr/include/c++/9/bits/move.h' line='99' column='1'
           visibility='default' binding='global' size-in-bits='64'>

        Notable attributes:
            DW_AT_external (parsed in common) is a flag present if the variable
              is visible outside of its compilation unit.
            DW_AT_explicit: "The member function will have a DW_AT_explicit attribute with
              the value true if that member function was marked with the
              explicit keyword in the source."
            DW_AT_defaulted: Whether a member function has been declared as default
            DW_AT_declaration: "A data object entry representing a non-defining
              declaration of the object will not have allocation attribute,
              and will have this attribute.
            DW_AT_pointer: For member functions which are not static, this
              attribute is used on the DW_TAG_subprogram to specify the "this"
              pointer (for C++) or the "self" pointer (in Objective C/C++).

        Not included:
           |DW_AT_declaration :  AttributeValue(name='DW_AT_declaration', form='DW_FORM_flag_present', value=True, raw_value=b'', offset=693)
           |DW_AT_object_pointer:  AttributeValue(name='DW_AT_object_pointer', form='DW_FORM_ref4', value=698, raw_value=698, offset=694)
        """
        pass

    def _parse_variable(self, corpus, die, tag):
        """
        Parse a variable.

        This also has DW_AT_type, which likely is used to determine
        it's a variable. Note usage: https://github.com/eliben/pyelftools/issues/27

        Not included:
           DW_AT_type: (probably already parsed to know it's a variable?)
           DW_AT_declaration: "A data object entry representing a non-defining
              declaration of the object will not have allocation attribute,
              and will have this attribute.

        """
        pass

    def _parse_typedef(self, corpus, die, tag):
        """parse a DW_TAG_typedef.

        An example xml is the following:
        <typedef-decl name='value_type' type-id='type-id-5'
                      filepath='/usr/include/c++/9/type_traits'
                      line='60' column='1' id='type-id-4987'/>
        We use the DW_AT_file number to look up the filename in the CompileUnit
        lineprogram for the CU. Most attributes here are included in common.
        """
        pass

    def _parse_union_type(self, corpus, die, tag):
        """parse a union type
        <union-decl name='__anonymous_union__' size-in-bits='64'
          is-anonymous='yes' visibility='default'
          filepath='/libabigail-1.8/build/../include/abg-ir.h'
          line='2316' column='1' id='type-id-2748'>

        DW_AT_sibling is not used. I'm not sure how to derive:
         - is-anonymoys
         - visibility
        """
        pass

    def _parse_base_type(self, corpus, die, tag):
        """parse a DW_TAG_base_type. Here is the xml equivalent"

        # <type-decl name='__float128' size-in-bits='128' id='type-id-32691'/>
        """
        pass

    def _parse_class_type(self, corpus, die, tag):
        """
        Parse a DW_TAG_class type.

        Assumption: a being called a class and not a struct indicates struct is false
        DW_AT_sibling is not included.
        TODO: It's not clear how to get visibility "default" here as shown above
        """
        tag = die.tag.lower()
        self.gen.fact(
            AspFunction(tag + "_is_struct", args=[corpus.path, die.unique_id, "no"])
        )

    def _parse_structure_type(self, corpus, die, tag):
        """DW_TAG_structure, example xml:

        <class-decl name='filter_base' size-in-bits='192' is-struct='yes'
                    visibility='default'
                    filepath='/libabigail-1.8/build/../include/abg-comp-filter.h'
                    line='120' column='1' id='type-id-1'>

        Since a struct is akin to a class, we automatically add "is_struct" to
        incidate this. We also don't use the "DW_AT_sibling" attribute:

        |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=705, raw_value=705, offset=677)

        This attribute looks like it's used to find the next CU offset.
        https://github.com/eliben/pyelftools/blob/46187f45f6085c8e28b7878c4058283d3ba5b812/elftools/dwarf/compileunit.py#L156
        TODO: also not sure how libabigail derives visibility here.
        """
        tag = die.tag.lower()
        self.gen.fact(
            AspFunction(tag + "_is_struct", args=[corpus.path, die.unique_id, "yes"])
        )

    def _parse_member(self, corpus, die, tag):
        """DW_TAG_member seems to be nested as follows:

        <data-member access='private' layout-offset-in-bits='0'>
        <var-decl name='_M_ptr' type-id='type-id-202' visibility='default'
            filepath='/usr/include/c++/9/bits/shared_ptr_base.h' line='1404' column='1'/>
        </data-member>

        Most attributes are represented in common except for:
          DW_AT_data_member_location. It looks like for this attribute, if
          form is in "DW_FORM_data4" or "DW_FORM_data8" there is a location list
          I am mostly seeing DW_FORM_data1, which looks like it means just
          grabbing the entire value:
          https://github.com/eliben/pyelftools/blob/46187f45f6085c8e28b7878c4058283d3ba5b812/elftools/dwarf/descriptions.py#L244
          https://github.com/eliben/pyelftools/blob/46187f45f6085c8e28b7878c4058283d3ba5b812/elftools/dwarf/descriptions.py#L172
        TODO: where is visibility? Private?
        """
        pass

    def _parse_parameter(self, corpus, die, tag):
        """
        Parse a DW_TAG_parameter.

         example xml is: <parameter type-id='type-id-28' is-artificial='yes'/>
        """
        artificial = False
        if hasattr(die.attributes, "DW_AT_artificial"):
            artificial = die.attributes["DW_AT_artificial"].value

        # TODO default value
        if "DW_AT_default_value" in die.attributes:
            print("Found default value!")
            import IPython

            IPython.embed()

        # Note that we aren't adding the negation, e.g., artificial == "no"
        # This is a strategy to generate fewer facts, but if we need it we can add.
        if artificial:
            tag = die.tag.lower()
            self.gen.fact(
                AspFunction(
                    tag + "_is_artificial", args=[corpus.path, die.unique_id, "yes"]
                )
            )

    def _parse_inheritance(self, corpus, die, tag):
        # Not sure what this gets parsed into
        # OrderedDict([('DW_AT_type',
        # AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=8855, raw_value=8855, offset=774)),
        # ('DW_AT_data_member_location',
        # AttributeValue(name='DW_AT_data_member_location', form='DW_FORM_data1', value=0, raw_value=0, offset=778))])
        print("PARSE INHERITANCE")
        import IPython

        IPython.embed()
        sys.exit(0)

        return {}

    def _parse_enumeration_type(self, corpus, die, tag):
        """parse an enumeration type.

        The xml looks like this. This is just the outside wrapper of this:
        <enum-decl name='_Rb_tree_color' filepath='/usr/include/c++/9/bits/stl_tree.h'
          line='99' column='1' id='type-id-21300'>
          <underlying-type type-id='type-id-297'/>
          <enumerator name='_S_red' value='0'/>
          <enumerator name='_S_black' value='1'/>
        </enum-decl>

        DW_AT_sibling is not parsed.
        """
        pass

    def _parse_array_type(self, corpus, die, tag):
        """parse an array type. Example XML is:

        <array-type-def dimensions='1' type-id='type-id-444' size-in-bits='64' id='type-id-16411'>
          <subrange length='2' type-id='type-id-1073' id='type-id-20406'/>
        </array-type-def>

        DW_AT_sibling is not used
        """
        pass

    def _parse_enumerator(self, corpus, die, tag):
        """parse an enumerator, cild of an enum-dec. L

        ooks like:
        <enumerator name='_S_red' value='0'/>
        <enumerator name='_S_black' value='1'/>
        """
        pass

    def _parse_template_type_param(self, corpus, die, tag):
        """parse a template type param.

        I don't think this is represented in libabigail.

        DIE DW_TAG_template_type_param, size=9, has_children=False
        |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'_CharT', raw_value=2788, offset=7425)
        |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=375, raw_value=375, offset=7429)
        """
        pass

    def _parse_template_value_param(self, corpus, die, tag):
        """parse a template value param.

        This also doesn't seem to be represented in libabigail.

        DIE DW_TAG_template_value_param, size=10, has_children=False
        |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_string', value=b'__v', raw_value=b'__v', offset=7884)
        |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=19248, raw_value=19248, offset=7888)
        |DW_AT_const_value :  AttributeValue(name='DW_AT_const_value', form='DW_FORM_data1', value=0, raw_value=0, offset=7892)
        """
        pass

    def _parse_subrange_type(self, corpus, die, tag):
        """I'm not sure if we need to do additional parsing of the upper bound?

        <subrange length='2' type-id='type-id-1073' id='type-id-20406'/>

        It looks like if DW_AT_lower bound is missing, it defaults to something
        language specific (0 or 1): http://dwarfstd.org/ShowIssue.php?issue=080516.1
        We probably need a more solid way to do this, for now I'm just doing 0/1
        """
        tag = die.tag.lower()

        # Fortran defaults to 1
        lower_bound = 0 if "fortran" not in self.language else 1
        if "DW_AT_lower_bound" in die.attributes:
            lower_bound = die.attributes["DW_AT_lower_bound"]

        # We can only parse a length with an upper and lower bound
        # There are some entries that are just empty, not sure why
        if "DW_AT_upper_bound" in die.attributes:
            upper_bound = die.attributes["DW_AT_upper_bound"].value

            # TODO need to check this, I remember reading it and can't find it again!
            length = upper_bound - lower_bound + 1
            self.gen.fact(
                AspFunction(tag + "_length", args=[corpus.path, die.unique_id, length])
            )

    def _parse_imported_module(self, corpus, die, tag):
        """Parsed imported module information.

        I don't see that this is mapped into libabigail. Most of the attributes
        are covered in common, but there is one extra we
        don't include:

        |DW_AT_import      :  AttributeValue(name='DW_AT_import', form='DW_FORM_ref4', value=734, raw_value=734, offset=7463)

        This can be used as follows (and I don't think it derives anything of
        value):

        from elftools.dwarf.descriptions import _import_extra
        _import_extra(die.attributes['DW_AT_import'], die, die.offset)
        '[Abbrev Number: 3 (DW_TAG_namespace)]'
        """
        pass

    def _parse_imported_declaration(self, corpus, die, tag):
        """Parse an imported declaration.

        The same is true as for _parse_imported_module. The value of the
        DW_AT_import is '[Abbrev Number: 27 (DW_TAG_typedef)]'. I suspect
        this means (for the first) we are importing a namespace, and for
        the second we are importing a typedef. This matches logically to
        "module" and "declaration" and we aren't includin as atoms for now.
        """
        pass

    def _parse_inlined_subroutine(self, corpus, die, tag):
        """Not sure what this goes into, maybe a function?
        DIE DW_TAG_inlined_subroutine, size=34, has_children=True
        |DW_AT_abstract_origin:  AttributeValue(name='DW_AT_abstract_origin', form='DW_FORM_ref4', value=25014, raw_value=25014, offset=24772)
        |DW_AT_entry_pc    :  AttributeValue(name='DW_AT_entry_pc', form='DW_FORM_addr', value=1111092, raw_value=1111092, offset=24776)
        |8504              :  AttributeValue(name=8504, form='DW_FORM_data1', value=0, raw_value=0, offset=24784)
        |DW_AT_low_pc      :  AttributeValue(name='DW_AT_low_pc', form='DW_FORM_addr', value=1111092, raw_value=1111092, offset=24785)
        |DW_AT_high_pc     :  AttributeValue(name='DW_AT_high_pc', form='DW_FORM_data8', value=10, raw_value=10, offset=24793)
        |DW_AT_call_file   :  AttributeValue(name='DW_AT_call_file', form='DW_FORM_data1', value=1, raw_value=1, offset=24801v)
        |DW_AT_call_line   :  AttributeValue(name='DW_AT_call_line', form='DW_FORM_data2', value=381, raw_value=381, offset=24802)
        |DW_AT_call_column :  AttributeValue(name='DW_AT_call_column', form='DW_FORM_data1', value=9, raw_value=9, offset=24804)
        """
        print("PARSE INLINED SUBROUTINE")
        print("This attribute has not been seen (and thus not developed yet)")
        import IPython

        IPython.embed()
        sys.exit(0)

    def _parse_subroutine_type(self, corpus, die, tag):
        """Not sure what a subroutine type is

        We don't use DW_AT_sibling.
        DIE DW_TAG_subroutine_type, size=9, has_children=True
        |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=153, raw_value=153, offset=18354)
        |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=18373, raw_value=18373, offset=18358)
        """
        pass

    def _parse_unspecified_type(self, corpus, die, tag):
        """Also not sure what this gets parsed into
        DIE DW_TAG_unspecified_type, size=6, has_children=False
        |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'decltype(nullptr)', raw_value=12681, offset=19244)
        """
        pass

    def _parse_reference_type(self, corpus, die, tag):
        """
        Parse a reference type.

        The xml looks like:
        <reference-type-def kind='lvalue' type-id='type-id-20945' size-in-bits='64' id='type-id-20052'/>

        # TODO: Is this an lvalue?
        """
        tag = die.tag.lower()
        self.gen.fact(
            AspFunction(tag + "_type", args=[corpus.path, die.unique_id, "lvalue"])
        )

    def _parse_rvalue_reference_type(self, corpus, die, tag):
        tag = die.tag.lower()
        self.gen.fact(
            AspFunction(tag + "_type", args=[corpus.path, die.unique_id, "rvalue"])
        )

    def _parse_volatile_type(self, corpus, die, tag):
        """Not sure what this gets parsed into
        DIE DW_TAG_volatile_type, size=6, has_children=False
        |DW_AT_type        :  AttributeValue(name='DW_AT_type', form='DW_FORM_ref4', value=22671, raw_value=22671, offset=22685)
        """
        pass

    def _parse_template_parameter_pack(self, corpus, die, tag):
        """

        not sure what this goes into - I don't think libabigail uses it.
        DIE DW_TAG_GNU_template_parameter_pack, size=9, has_children=True
        |DW_AT_name        :  AttributeValue(name='DW_AT_name', form='DW_FORM_strp', value=b'_Args', raw_value=1841328, offset=39845)
        |DW_AT_sibling     :  AttributeValue(name='DW_AT_sibling', form='DW_FORM_ref4', value=11585, raw_value=11585, offset=39849)
        """
        print("PARSE TEMPLATE PARAMETER")
        print("This attribute has not been seen (and thus not developed yet)")
        import IPython

        IPython.embed()
        sys.exit(0)

    def _parse_gnu_call_site(self, corpus, die, tag):
        """Not sure what this is
        DIE DW_TAG_GNU_call_site, size=13, has_children=True
        |DW_AT_low_pc      :  AttributeValue(name='DW_AT_low_pc', form='DW_FORM_addr', value=1111102, raw_value=1111102, offset=24919)
        |DW_AT_GNU_tail_call:  AttributeValue(name='DW_AT_GNU_tail_call', form='DW_FORM_flag_present', value=True, raw_value=b'', offset=24927)
        |DW_AT_abstract_origin:  AttributeValue(name='DW_AT_abstract_origin', form='DW_FORM_ref4', value=28213, raw_value=28213, offset=24927)
        """
        print("PARSE GNU CALL SITE")
        import IPython

        IPython.embed()
        sys.exit(0)

        dmeta = {"_type": "gnu-call-site"}
        if die.has_children:
            dmeta["children"] = []
        return dmeta

    def _parse_lexical_block(self, corpus, die, tag):
        """Not sure where this goes!"""

        print("PARSE LEXICAL BLOCK")
        print("This attribute has not been seen (and thus not developed yet)")
        import IPython

        IPython.embed()
        sys.exit(0)

    def _parse_gnu_call_site_parameter(self, corpus, die, tag):
        """
        DIE DW_TAG_GNU_call_site_parameter, size=7, has_children=False
        |DW_AT_location    :  AttributeValue(name='DW_AT_location', form='DW_FORM_exprloc', value=[85], raw_value=[85], offset=24932)
        |DW_AT_GNU_call_site_value:  AttributeValue(name='DW_AT_GNU_call_site_value', form='DW_FORM_exprloc', value=[243, 1, 85], raw_value=[243, 1, 85], offset=24934)
        """
        print("PARSE GNU CALL")
        print("This attribute has not been seen (and thus not developed yet)")
        import IPython

        IPython.embed()
        sys.exit(0)

    def _parse_const_type(self, corpus, die, tag):
        """Parse a constant type.

        Note that this has DW_AT_type, which possibly has issues for pyelftools
        (but I'm not sure we use it?)
        https://github.com/eliben/pyelftools/issues/27
        """
        tag = die.tag.lower()
        self.gen.fact(
            AspFunction(tag + "_const", args=[corpus.path, die.unique_id, "yes"])
        )

    def _parse_pointer_type(self, corpus, die, tag):
        """parse a pointer type"""
        pass

    def generate_corpus_metadata(self, corpora, prefix=""):
        """Given a list of corpora, create a fact for each one. If we need them,
        we can add elfheaders here.
        """
        prefix = "%s_" % prefix if prefix else ""

        # Use the corpus path as a unique id (ok if binaries exist)
        # This would need to be changed if we don't have the binary handy
        for corpus in corpora:
            hdr = corpus.elfheader

            self.gen.h2("Corpus facts: %s" % corpus.path)

            self.gen.fact(fn.corpus(corpus.path))
            self.gen.fact(AspFunction(prefix + "corpus", args=[corpus.path]))
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_name",
                    args=[corpus.path, os.path.basename(corpus.path)],
                )
            )

            # e_ident is ELF identification
            # https://docs.oracle.com/cd/E19683-01/816-1386/chapter6-35342/index.html
            # Note that we could update these to just be corpus_attr, but I'm
            # starting with testing a more detailed approach for now.

            # If the corpus has a soname:
            if corpus.soname:
                self.gen.fact(
                    AspFunction(
                        prefix + "corpus_soname", args=[corpus.path, corpus.soname]
                    )
                )

            # File class (also at elffile.elfclass or corpus.elfclass
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_elf_class",
                    args=[corpus.path, hdr["e_ident"]["EI_CLASS"]],
                )
            )

            # Data encoding
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_data_encoding",
                    args=[corpus.path, hdr["e_ident"]["EI_DATA"]],
                )
            )

            # File version
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_file_version",
                    args=[corpus.path, hdr["e_ident"]["EI_VERSION"]],
                )
            )

            # Operating system / ABI Information
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_elf_osabi",
                    args=[corpus.path, hdr["e_ident"]["EI_OSABI"]],
                )
            )

            # Abi Version
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_abiversion",
                    args=[corpus.path, hdr["e_ident"]["EI_ABIVERSION"]],
                )
            )

            # e_type is the object file type
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_elf_type", args=[corpus.path, hdr["e_type"]]
                )
            )

            # e_machine is the required architecture for the file
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_elf_machine", args=[corpus.path, hdr["e_machine"]]
                )
            )

            # object file version
            self.gen.fact(
                AspFunction(
                    prefix + "corpus_elf_version", args=[corpus.path, hdr["e_version"]]
                )
            )

            # Not included (and we could add?)
            # virtual address where system transfers control, if no entry, will find 0
            # 'e_entry': 4160, <-- this is likely important

            # program header table's file offset (bytes), 0 if none
            # 'e_phoff': 64,

            # section header table's offset, also in bytes (0 if none)
            # 'e_shoff': 15672,

            # processor-specific flags associated with the file (0 if none)
            # 'e_flags': 0,

            # elf header size in bytes
            # 'e_ehsize': 64,

            # size in bytes of one entry in file's program header
            # 'e_phentsize': 56,

            # number of entries in program header table
            # 'e_phnum': 11,

            # section header's size in bytes
            # 'e_shentsize': 64,

            # number of entries in section header table
            # 'e_shnum': 30,

            # section header table index of entry associated with section name string table
            # 'e_shstrndx': 29

    def setup(self, driver, corpora, tests=False):
        """
        Generate an ASP program with relevant constraints for a binary
        and a library, for which we have been provided their corpora.

        This calls methods on the solve driver to set up the problem with
        facts and rules from both corpora, and rules that determine ABI
        compatibility.

        Arguments:
            corpora: [corpusA, corpusB, corpusC]
            corpusA (corpus.Corpus): the first corpus for the binary
            corpusB (corpus.Corpus): the corpus for the library that works
            corpusB (corpus.Corpus): the corpus for the library that we test

        """
        # Pull out corpus groups. This is the library known to work
        library = corpora[1]

        # This is the binary and library in question
        corpora = [corpora[0], corpora[2]]

        # Every fact, entity that we make needs a unique id
        # Note that this isn't actually in use yet!
        self._condition_id_counter = itertools.count()

        # preliminary checks
        for corpus in corpora:
            assert corpus.exists()

        # driver is used by all the functions below to add facts and
        # rules to generate an ASP program.
        self.gen = driver

        self.gen.h1("Corpus Facts")

        # Generate high level corpus metadata facts (e.g., header)
        self.generate_corpus_metadata(corpora)
        self.generate_corpus_metadata([library], prefix="needed")

        # Dynamic libraries that are needed
        self.generate_needed(corpora)

        # generate all elf symbols (might be able to make this smaller set)
        self.generate_elf_symbols(corpora)

        # Generate the same for the known working library, but with a prefix
        self.generate_elf_symbols([library], prefix="needed")

        # Generate dwarf information entries
        self.generate_dwarf_information_entries(corpora)

        # Generate dwarf information entries for needed
        self.generate_dwarf_information_entries([library], prefix="needed")


# Internal helper functions


def _get_die_filepath(die):
    """
    If we find DW_AT_decl_file in the attributes, we need to get the
    associated filename.
    """
    filepath = None
    if "DW_AT_decl_file" in die.attributes:
        index = die.attributes["DW_AT_decl_file"].value

        # TODO: need to debug why this fails sometimes
        try:
            filepath = get_cu_filename(die.cu, index)
        except:
            pass
    return filepath


def _get_cu_filename(cu, idx=0):
    """
    A DW_AT_decl_file I think can be looked up, by index, from the CU
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


# Functions intended to be called by external clients


def generate_facts(libs):
    """A single function to print facts for one or more corpora."""
    if not isinstance(libs, list):
        libs = [libs]

    parser = ABIParser()
    setup = ABICompatSolverSetup()
    driver = PyclingoDriver()
    corpora = []
    for lib in libs:
        corpora.append(parser.get_corpus_from_elf(lib))
    return driver.solve(setup, corpora, facts_only=True)


def is_compatible(
    binary,
    libraryA,
    libraryB,
    dump=(),
    models=0,
    timers=False,
    stats=False,
    tests=False,
    logic_programs=None,
):
    """
    Given three libraries (we call one a main binary and the other a library
    that works, and the second one that we want to link with it), determine
    if the second library is compatible with the binary. This wrapper function,
    in requiring the three named arguments for binary, libraryA and libraryB,
    enforces that all three are provided (and in the correct order).
    If the functions for the solver are used outside this context, make sure
    that you provide them in the correct order.

    Arguments:
        binary (str): path to a binary to assess for compataibility
        libraryA (str): path to a library that is known to work
        libraryB (str): a second library to assess for compatability.
        dump (tuple): what to dump
        models (int): number of models to search (default: 0)
    """
    driver = PyclingoDriver()
    if "asp" in dump:
        driver.out = sys.stdout

    for path in [binary, library]:
        if not os.path.exists(path):
            sys.exit("%s does not exist." % path)

    # Create the parser, and generate the corpora
    parser = ABIParser()
    corpusA = parser.get_corpus_from_elf(binary)
    corpusB = parser.get_corpus_from_elf(libraryA)
    corpusC = parser.get_corpus_from_elf(libraryB)
    setup = ABICompatSolverSetup()

    # The order should be binary | working library | library
    return driver.solve(
        setup,
        [corpusA, corpusB, corpusC],
        dump,
        models,
        timers,
        stats,
        tests,
        logic_programs,
    )
