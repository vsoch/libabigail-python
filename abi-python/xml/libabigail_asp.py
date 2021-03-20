# This is based on asp.py from spack/spack, copyright LLNL and spack developers
# It will eventually be added back to that scope - this script is developing
# new functionality to work with ABI.

import collections
import copy
import itertools
import os
import pprint
import sys
import time
import types
import xmltodict
from six import string_types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import clingo

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


def all_compilers_in_config():
    return spack.compilers.all_compilers()


def extend_flag_list(flag_list, new_flags):
    """Extend a list of flags, preserving order and precedence.

    Add new_flags at the end of flag_list.  If any flags in new_flags are
    already in flag_list, they are moved to the end so that they take
    higher precedence on the compile line.

    """
    for flag in new_flags:
        if flag in flag_list:
            flag_list.remove(flag)
        flag_list.append(flag)


def check_same_flags(flag_dict_1, flag_dict_2):
    """Return True if flag dicts contain the same flags regardless of order."""
    types = set(flag_dict_1.keys()).union(set(flag_dict_2.keys()))
    for t in types:
        values1 = set(flag_dict_1.get(t, []))
        values2 = set(flag_dict_2.get(t, []))
        assert values1 == values2


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


def _normalize_packages_yaml(packages_yaml):
    normalized_yaml = copy.copy(packages_yaml)
    for pkg_name in packages_yaml:
        is_virtual = spack.repo.path.is_virtual(pkg_name)
        if pkg_name == "all" or not is_virtual:
            continue

        # Remove the virtual entry from the normalized configuration
        data = normalized_yaml.pop(pkg_name)
        is_buildable = data.get("buildable", True)
        if not is_buildable:
            for provider in spack.repo.path.providers_for(pkg_name):
                entry = normalized_yaml.setdefault(provider.name, {})
                entry["buildable"] = False

        externals = data.get("externals", [])
        keyfn = lambda x: spack.spec.Spec(x["spec"]).name
        for provider, specs in itertools.groupby(externals, key=keyfn):
            entry = normalized_yaml.setdefault(provider, {})
            entry.setdefault("externals", []).extend(specs)

    return normalized_yaml


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
        binary_xml,
        library_xml,
        dump=None,
        nmodels=0,
        timers=False,
        stats=False,
        tests=False,
        logic_programs=None,
    ):
        """Given two corpora, determine if they are compatible by way of
        flattening header information into facts, and handing to a solver.
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
            solver_setup.setup(self, binary_xml, library_xml, tests=tests)
        timer.phase("setup")

        # read in the main ASP program and display logic -- these are
        # handwritten, not generated, so we load them as resources
        parent_dir = os.path.dirname(__file__)
        # self.control.load(os.path.join(parent_dir, 'compatible.lp'))
        # self.control.load(os.path.join(parent_dir, "display.lp"))
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

        solve_kwargs = {}
        # Won't work after this, need to write files
        # solve_kwargs = {
        #    "assumptions": self.assumptions,
        #    "on_model": on_model,
        #    "on_core": cores.append,
        # }
        # if clingo_cffi:
        #    solve_kwargs["on_unsat"] = cores.append
        # solve_result = self.control.solve(**solve_kwargs)
        # timer.phase("solve")

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

    def condition(self, required_spec, imposed_spec=None, name=None):
        """Generate facts for a dependency or virtual provider condition.
        TODO: this should be updated to be a condition for ABI (not
        sure what that looks like yet).

        Arguments:
            required_spec (Spec): the spec that triggers this condition
            imposed_spec (optional, Spec): the sepc with constraints that
                are imposed when this condition is triggered
            name (optional, str): name for `required_spec` (required if
                required_spec is anonymous, ignored if not)

        Returns:
            (int): id of the condition created by this function
        """
        named_cond = required_spec.copy()
        named_cond.name = named_cond.name or name
        assert named_cond.name, "must provide name for anonymous condtions!"

        condition_id = next(self._condition_id_counter)
        self.gen.fact(fn.condition(condition_id))

        # requirements trigger the condition
        requirements = self.checked_spec_clauses(
            named_cond, body=True, required_from=name
        )
        for pred in requirements:
            self.gen.fact(fn.condition_requirement(condition_id, pred.name, *pred.args))

        if imposed_spec:
            imposed_constraints = self.checked_spec_clauses(
                imposed_spec, body=False, required_from=name
            )
            for pred in imposed_constraints:
                # imposed "node"-like conditions are no-ops
                if pred.name in ("node", "virtual_node"):
                    continue
                self.gen.fact(
                    fn.imposed_constraint(condition_id, pred.name, *pred.args)
                )

        return condition_id

    def _generate_type_decl(self, corpus, data):
        """A type declaration has a unique id (generated by libabigail, and
        typically a name and size in bits.

        type_decl("type-id-25").
        type_decl_name("type-id-25","wchar_t").
        type_decl_size_in_bits("type-id-25","32").
        has_type_decl("/code/simple-example/cpp/math-client","type-id-25").

        """
        for entry in data:
            self.gen.fact(fn.type_decl(entry["@id"]))
            self.gen.fact(fn.type_decl_name(entry["@id"], entry["@name"]))

            # Not all entries have size in bits
            if "@size-in-bits" in entry:
                self.gen.fact(
                    fn.type_decl_size_in_bits(entry["@id"], entry["@size-in-bits"])
                )
            self.gen.fact(fn.has_type_decl(corpus, entry["@id"]))

    def _generate_array_type_def(self, corpus, data):
        """An array type definition usually has an id, size in bits, dimension,
        and subrange.

        array_type_def("type-id-8").
        array_type_def_type("type-id-8","type-id-2").
        array_type_def_size_in_bits("type-id-8","32").
        array_type_def_dimensions("type-id-8","1").
        subrange("type-id-9").
        has_subrange("type-id-8","type-id-9").
        subrange_length("type-id-9","4").
        subrange_type("type-id-9","type-id-4").
        has_array_type_decl("/code/simple-example/cpp/math-client","type-id-8").

        """
        for entry in data:
            self.gen.fact(fn.array_type_def(entry["@id"]))
            self.gen.fact(fn.array_type_def_type(entry["@id"], entry["@type-id"]))
            self.gen.fact(
                fn.array_type_def_size_in_bits(entry["@id"], entry["@size-in-bits"])
            )
            self.gen.fact(
                fn.array_type_def_dimensions(entry["@id"], entry["@dimensions"])
            )

            # Add the subrange
            self.gen.fact(fn.subrange(entry["subrange"]["@id"]))
            self.gen.fact(fn.has_subrange(entry["@id"], entry["subrange"]["@id"]))
            self.gen.fact(
                fn.subrange_length(
                    entry["subrange"]["@id"], entry["subrange"]["@length"]
                )
            )
            self.gen.fact(
                fn.subrange_type(
                    entry["subrange"]["@id"], entry["subrange"]["@type-id"]
                )
            )
            self.gen.fact(fn.has_array_type_decl(corpus, entry["@id"]))

    def _generate_class_decl(self, corpus, data):
        """generate class declaration facts

        class_decl("type-id-56").
        class_decl_name("type-id-56","__anonymous_struct__4").
        class_decl_size_in_bits("type-id-56","128").
        class_decl_is_struct("type-id-56","yes").
        class_decl_visibility("type-id-56","default").
        class_data_member("type-id-56","__pos").
        class_data_member_type("type-id-56","__pos","type-id-34").
        class_data_member_visibility("type-id-56","__pos","default").
        class_data_member_layout_offset_bits("type-id-56","__pos","0").
        class_data_member_access("type-id-56","__pos","public").
        class_data_member("type-id-56","__state").
        class_data_member_type("type-id-56","__state","type-id-40").
        class_data_member_visibility("type-id-56","__state","default").
        class_data_member_layout_offset_bits("type-id-56","__state","64").
        class_data_member_access("type-id-56","__state","public").

        """
        for entry in data:
            self.gen.fact(fn.class_decl(entry["@id"]))
            self.gen.fact(fn.class_decl_name(entry["@id"], entry["@name"]))
            self.gen.fact(
                fn.class_decl_size_in_bits(entry["@id"], entry["@size-in-bits"])
            )
            self.gen.fact(fn.class_decl_is_struct(entry["@id"], entry["@is-struct"]))
            self.gen.fact(fn.class_decl_visibility(entry["@id"], entry["@visibility"]))
            self.gen.fact(fn.has_class_decl(corpus, entry["@id"]))

            # Add data members
            for member in entry.get("data-member", []):
                if "var-decl" not in member:
                    print(
                        "% Warning, var-decl not in member. Keys include "
                        + " ".join(member.keys())
                    )
                    continue

                # Data members don't appear to have unique ids, so we describe them
                # as a paired value with class id and member name
                name = member["var-decl"]["@name"]
                self.gen.fact(fn.class_data_member(entry["@id"], name))
                self.gen.fact(
                    fn.class_data_member_type(
                        entry["@id"], name, member["var-decl"]["@type-id"]
                    )
                )
                self.gen.fact(
                    fn.class_data_member_visibility(
                        entry["@id"], name, member["var-decl"]["@visibility"]
                    )
                )
                self.gen.fact(
                    fn.class_data_member_layout_offset_bits(
                        entry["@id"], name, member["@layout-offset-in-bits"]
                    )
                )
                self.gen.fact(
                    fn.class_data_member_access(entry["@id"], name, member["@access"])
                )

    def _generate_typedef_decl(self, corpus, data):
        """Generate typedef declaration facts

        typedef_decl("type-id-60").
        typedef_decl_type("type-id-60","type-id-15").
        typedef_decl_name("type-id-60","__int32_t").
        typedef_decl_filepath("type-id-60","/usr/include/x86_64-linux-gnu/bits/types.h").
        typedef_decl_line("type-id-60","40").
        typedef_decl_column("type-id-60","1").

        """
        for entry in data:
            self.gen.fact(fn.typedef_decl(entry["@id"]))
            self.gen.fact(fn.typedef_decl_type(entry["@id"], entry["@type-id"]))
            self.gen.fact(fn.typedef_decl_name(entry["@id"], entry["@name"]))
            self.gen.fact(fn.typedef_decl_filepath(entry["@id"], entry["@filepath"]))
            self.gen.fact(fn.typedef_decl_line(entry["@id"], entry["@line"]))
            self.gen.fact(fn.typedef_decl_column(entry["@id"], entry["@column"]))
            self.gen.fact(fn.has_typedef_decl(corpus, entry["@id"]))

    def _generate_pointer_type_def(self, corpus, data):
        """Generate pointer type definition facts

        pointer_type_def("type-id-105").
        pointer_type_def_type("type-id-105","type-id-104").
        pointer_type_def_size_in_bits("type-id-105","64").

        """
        for entry in data:
            self.gen.fact(fn.pointer_type_def(entry["@id"]))
            self.gen.fact(fn.pointer_type_def_type(entry["@id"], entry["@type-id"]))
            self.gen.fact(
                fn.pointer_type_def_size_in_bits(entry["@id"], entry["@size-in-bits"])
            )
            self.gen.fact(fn.has_pointer_decl(corpus, entry["@id"]))

    def _generate_qualified_type_def(self, corpus, data):
        """Generate facts for qualified type defs

        qualified_type_def("type-id-91").
        qualified_type_def_const("type-id-91","yes").
        qualified_type_def_type("type-id-91","type-id-25").
        has_qualified_type_def("/code/simple-example/cpp/math-client","type-id-91").

        """
        for entry in data:
            self.gen.fact(fn.qualified_type_def(entry["@id"]))
            self.gen.fact(fn.qualified_type_def_const(entry["@id"], entry["@const"]))
            self.gen.fact(fn.qualified_type_def_type(entry["@id"], entry["@type-id"]))
            self.gen.fact(fn.has_qualified_type_def(corpus, entry["@id"]))

    def _generate_reference_type_def(self, corpus, data):
        """Add reference type declaration facts

        reference_type_def("type-id-99").
        reference_type_def_type("type-id-99","type-id-75").
        reference_type_def_size_in_bits("type-id-99","64").
        reference_type_def_kind("type-id-99","rvalue").
        has_reference_type_def("/code/simple-example/cpp/math-client","type-id-99").

        """
        for entry in data:
            self.gen.fact(fn.reference_type_def(entry["@id"]))
            self.gen.fact(fn.reference_type_def_type(entry["@id"], entry["@type-id"]))
            self.gen.fact(
                fn.reference_type_def_size_in_bits(entry["@id"], entry["@size-in-bits"])
            )
            self.gen.fact(fn.reference_type_def_kind(entry["@id"], entry["@kind"]))
            self.gen.fact(fn.has_reference_type_def(corpus, entry["@id"]))

    def _generate_namespace_decl(self, corpus, data):
        print("namespace decl")
        print("TODO: this has nesting")
        import IPython

        IPython.embed()

    def _generate_function_decl(self, corpus, data):
        print("function decl")
        import IPython

        IPython.embed()

    def _generate_function_type(self, corpus, data):
        print("function type")
        import IPython

        IPython.embed()

    def generate_dwarf_info_entries(self, corpora):
        """Given a list of corpora, parse nested abi-instr"""

        for corpus in corpora:
            instr = corpus.get("abi-instr", {})
            if not instr:
                continue

            # This currently assumes abigail consistently provides these attributes
            self.gen.fact(fn.corpus_abigail_version(corpus["@path"], instr["@version"]))
            self.gen.fact(
                fn.corpus_address_size(corpus["@path"], instr["@address-size"])
            )
            self.gen.fact(
                fn.corpus_compile_directory(corpus["@path"], instr["@comp-dir-path"])
            )
            self.gen.fact(fn.corpus_language(corpus["@path"], instr["@language"]))

            # For each remaining type, generate facts
            for attr in list(instr.keys()):

                # @ are properties, such as those we parsed above
                if attr.startswith("@"):
                    continue

                # Dynamically derive function names
                func_name = "_generate_%s" % attr.replace("-", "_")

                # Warn if we are missing parsing something!
                if not hasattr(self, func_name):
                    print("% Warning, missing parsing of %s" % attr)

                # The corpus path is it's unique identifier
                getattr(self, func_name)(corpus["@path"], instr[attr])

    # TODO: what would a condition be here for ABI?
    #            condition_id = self.condition(cond, dep.spec, pkg.name)
    #                self.gen.fact(fn.dependency_condition(
    #                    condition_id, pkg.name, dep.spec.name
    #                ))

    def generate_corpus_symbols(self, corpora):
        """Given function and variable symbols from the xml, dump them as facts"""
        for corpus in corpora:

            # Elf function symbols
            symbols = corpus.get("elf-function-symbols", {}).get("elf-symbol", [])
            if not isinstance(symbols, list):
                symbols = [symbols]

            for symbol in symbols:
                self.gen.fact(fn.symbol(symbol["@name"]))
                self.gen.fact(fn.symbol_type(symbol["@name"], symbol["@type"]))
                self.gen.fact(fn.symbol_binding(symbol["@name"], symbol["@binding"]))
                self.gen.fact(
                    fn.symbol_visibility(symbol["@name"], symbol["@visibility"])
                )
                self.gen.fact(
                    fn.symbol_is_defined(symbol["@name"], symbol["@is-defined"])
                )
                self.gen.fact(fn.has_symbol(corpus["@path"], symbol["@name"]))

            # Elf variable symbols (has added size)
            symbols = corpus.get("elf-variable-symbols", {}).get("elf-symbol", [])
            if not isinstance(symbols, list):
                symbols = [symbols]

            for symbol in symbols:

                self.gen.fact(fn.symbol(symbol["@name"]))
                self.gen.fact(fn.symbol_size(symbol["@name"], symbol["@size"]))
                self.gen.fact(fn.symbol_type(symbol["@name"], symbol["@type"]))
                self.gen.fact(fn.symbol_binding(symbol["@name"], symbol["@binding"]))
                self.gen.fact(
                    fn.symbol_visibility(symbol["@name"], symbol["@visibility"])
                )
                self.gen.fact(
                    fn.symbol_is_defined(symbol["@name"], symbol["@is-defined"])
                )
                self.gen.fact(fn.has_symbol(corpus["@path"], symbol["@name"]))

    def generate_corpus_metadata(self, corpora):
        """Given a list of corpora, create a fact for each one. This includes
        header information (e.g., needed) along with elf function and variable
        symbols.
        """
        # Use the corpus path as a unique id (ok if binaries exist)
        # This would need to be changed if we don't have the binary handy
        for corpus in corpora:

            self.gen.h2("Corpus facts: %s" % corpus["@path"])
            self.gen.fact(fn.corpus(corpus["@path"]))
            self.gen.fact(
                fn.corpus_architecture(corpus["@path"], corpus["@architecture"])
            )

            for needed in corpus.get("elf-needed", {}).get("dependency", []):
                self.gen.fact(fn.corpus_needs_library(corpus["@path"], needed["@name"]))

    def setup(self, driver, binary_xml, library_xml, tests=False):
        """Generate an ASP program with relevant constraints for a binary
        and a library, for which we have been provided their corpora.

        This calls methods on the solve driver to set up the problem with
        facts and rules from both corpora, and rules that determine ABI
        compatibility.

        Arguments:
            binary_xml (xml file): the first corpus
            library_xml (xml file): the second corpus

        """
        # Every fact, entity that we make needs a unique id
        self._condition_id_counter = itertools.count()

        # read in each corpus xml
        corpusA = load_xml(binary_xml).get("abi-corpus", {})
        corpusB = load_xml(library_xml).get("abi-corpus", {})

        # Cut out early if data is not correct
        if not corpusA or not corpusB:
            sys.exit("One or more corpora are malformed, missing abi-corpus.")

        # driver is used by all the functions below to add facts and
        # rules to generate an ASP program.
        self.gen = driver

        self.gen.h1("Corpus Facts")

        # Generate high level corpus metadata facts
        self.generate_corpus_metadata([corpusA, corpusB])

        # Elf function and variable symbols
        self.generate_corpus_symbols([corpusA, corpusB])

        # Generate dwarf information entries
        self.generate_dwarf_info_entries([corpusA, corpusB])


def load_xml(xml_file):
    with open(xml_file, "r") as fd:
        content = xmltodict.parse(fd.read())
    return content


def is_compatible(
    binary_xml,
    library_xml,
    dump=(),
    models=0,
    timers=False,
    stats=False,
    tests=False,
    logic_programs=None,
):
    """Given two dumps of library xml generated by libabigail, generate
    facts for each to then determine if the two are compatible.

    Arguments:
        binary_xml (str): path to libabigail xml for a binary
        library_xml (str): path to libabigail xml for a library
        dump (tuple): what to dump
        models (int): number of models to search (default: 0)
    """
    driver = PyclingoDriver()
    if "asp" in dump:
        driver.out = sys.stdout

    for path in [binary_xml, library_xml]:
        if not os.path.exists(path):
            sys.exit("%s does not exist." % path)

    # Create the parser, and generate the corpus
    setup = ABICompatSolverSetup()
    return driver.solve(
        setup,
        binary_xml,
        library_xml,
        dump,
        models,
        timers,
        stats,
        tests,
        logic_programs,
    )
