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
from six import string_types

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
        corpusA,
        corpusB,
        dump=None,
        nmodels=0,
        timers=False,
        stats=False,
        tests=False,
    ):
        """Given two corpora, determine if they are compatible by way of
        flattening header information into facts, and handing to a solver.
        """
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
            solver_setup.setup(self, corpusA, corpusB, tests=tests)
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

    def generate_dwarf_info_entries(self, corpora):
        """Iterate over the Dwarf Information Entires (DIEs) for each corpus,
        and add them as facts
        """
        # A helper function to generate a unique id for a DIE
        # corpus path + abbrev_code for the DIE
        def uid(corpus, die):
            return "%s:%s" % (corpus.path, die.abbrev_code)

        for corpus in corpora:

            self.gen.h2("Corpus DIE: %s" % corpus.path)
            if corpus.path not in self.die_lookup:
                self.die_lookup[corpus.path] = {}

            for entry in corpus.iter_dwarf_information_entries():

                # Skip entries without tags
                if not entry.tag:
                    continue

                if entry.abbrev_code not in self.die_lookup[corpus.path]:
                    pass
                    # TODO: not sure how to structure the relationship

                # Flatten attributes into dictionary

                # Try creating flattened entries for now
                unique_id = uid(corpus, entry)
                self.gen.fact(AspFunction(entry.tag, args=[unique_id]))

                # Do we need these relationships as facts?
                [
                    self.gen.fact(fn.has_child(unique_id, uid(corpus, child)))
                    for child in entry.iter_children()
                ]

                # Add all attributes
                # We could add others too:
                # AttributeValue(name='DW_AT_stmt_list',
                #                form='DW_FORM_sec_offset',
                #                value=0, raw_value=0, offset=41)
                for attr_name, attribute in entry.attributes.items():

                    # Ensure we don't write bytes
                    value = attribute.value
                    if isinstance(value, bytes):
                        value = value.decode('utf-8')

                    # DW_TAG_compiler_unit_attr
                    self.gen.fact(
                        AspFunction(
                            entry.tag + "_attr",
                            args=[unique_id, attr_name, value],
                        )
                    )
                    # DW_TAG_compiler_unit_form
                    self.gen.fact(
                        AspFunction(
                            entry.tag + "_form",
                            args=[unique_id, attr_name, attribute.form],
                        )
                    )

    def generate_elf_symbols(self, corpora):
        """For each corpus, write out elf symbols as facts. Note that we are
        trying a more detailed approach with facts/atoms being named (e.g.,
        symbol_type instead of symbol_attr). We could also try a simpler
        approach:

        symbol_type("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STT_FUNC").
        symbol_binding("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STB_FUNC").
        symbol_attr("_ZN11MathLibrary10Arithmetic8MultiplyEdd", "STV_default").

        """
        for corpus in corpora:
            self.gen.h2("Corpus symbols: %s" % corpus.path)
            for symbol, meta in corpus.elfsymbols.items():

                # It begins with a NULL symbol, not sure it's useful
                if not symbol:
                    continue

                self.gen.fact(fn.symbol(symbol))
                self.gen.fact(fn.symbol_type(symbol, meta["type"]))
                self.gen.fact(fn.symbol_binding(symbol, meta["binding"]))
                self.gen.fact(fn.symbol_visibility(symbol, meta["visibility"]))
                self.gen.fact(fn.has_symbol(corpus.path, symbol))

    def generate_needed(self, corpora):
        """Given a list of corpora, add needed libraries from dynamic tags."""
        for corpus in corpora:
            for needed in corpus.dynamic_tags.get("needed", []):
                self.gen.fact(fn.corpus_needs_library(corpus.path, needed))

    def generate_dwarf_information_entries(self, corpora):
        """Given a list of corpora, add needed libraries from dynamic tags."""
        for corpus in corpora:
            for entry in corpus.iter_dwarf_information_entries():
                self.gen.fact(fn.corpus_needs_library(corpus.path, needed))

    # TODO: what would a condition be here for ABI?
    #            condition_id = self.condition(cond, dep.spec, pkg.name)
    #                self.gen.fact(fn.dependency_condition(
    #                    condition_id, pkg.name, dep.spec.name
    #                ))

    def generate_corpus_metadata(self, corpora):
        """Given a list of corpora, create a fact for each one. If we need them,
        we can add elfheaders here.
        """
        # Use the corpus path as a unique id (ok if binaries exist)
        # This would need to be changed if we don't have the binary handy
        for corpus in corpora:
            hdr = corpus.elfheader

            self.gen.h2("Corpus facts: %s" % corpus.path)
            self.gen.fact(fn.corpus(corpus.path))

            # e_ident is ELF identification
            # https://docs.oracle.com/cd/E19683-01/816-1386/chapter6-35342/index.html
            # Note that we could update these to just be corpus_attr, but I'm
            # starting with testing a more detailed approach for now.

            # File class
            self.gen.fact(fn.corpus_elf_class(corpus.path, hdr["e_ident"]["EI_CLASS"]))

            # Data encoding
            self.gen.fact(
                fn.corpus_elf_data_encoding(corpus.path, hdr["e_ident"]["EI_DATA"])
            )

            # File version
            self.gen.fact(
                fn.corpus_elf_file_version(corpus.path, hdr["e_ident"]["EI_VERSION"])
            )

            # Operating system / ABI Information
            self.gen.fact(fn.corpus_elf_osabi(corpus.path, hdr["e_ident"]["EI_OSABI"]))

            # Abi Version
            self.gen.fact(
                fn.corpus_elf_abiversion(corpus.path, hdr["e_ident"]["EI_ABIVERSION"])
            )

            # e_type is the object file type
            self.gen.fact(fn.corpus_elf_type(corpus.path, hdr["e_type"]))

            # e_machine is the required architecture for the file
            self.gen.fact(fn.corpus_elf_machine(corpus.path, hdr["e_machine"]))

            # object file version
            self.gen.fact(fn.corpus_elf_version(corpus.path, hdr["e_version"]))

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

    def setup(self, driver, corpusA, corpusB, tests=False):
        """Generate an ASP program with relevant constraints for a binary
        and a library, for which we have been provided their corpora.

        This calls methods on the solve driver to set up the problem with
        facts and rules from both corpora, and rules that determine ABI
        compatibility.

        Arguments:
            corpusA (corpus.Corpus): the first corpus
            corpusB (corpus.Corpus): the second corpus

        """
        # Every fact, entity that we make needs a unique id
        self._condition_id_counter = itertools.count()

        # preliminary checks
        assert corpusA.exists()
        assert corpusB.exists()

        # driver is used by all the functions below to add facts and
        # rules to generate an ASP program.
        self.gen = driver

        self.gen.h1("Corpus Facts")

        # Generate high level corpus metadata facts (e.g., header)
        self.generate_corpus_metadata([corpusA, corpusB])

        # Dynamic libraries that are needed
        self.generate_needed([corpusA, corpusB])

        # generate all elf symbols (might be able to make this smaller set)
        self.generate_elf_symbols([corpusA, corpusB])

        # Generate dwarf information entries
        self.generate_dwarf_info_entries([corpusA, corpusB])


def is_compatible(
    binary, library, dump=(), models=0, timers=False, stats=False, tests=False
):
    """Given two libraries (we call one a main binary and the other a library
    that we want to link with it), determine if the two are compatible. This
    is currently written to support binaries, and ultimately we'd want to take
    two specs, and then to lookup the information we need in a database. We don't
    know what we need yet so we cannot do that.

    Arguments:
        binary (str): path to a binary to assess for compataibility
        library (str): path to a library to assess for compatability
        dump (tuple): what to dump
        models (int): number of models to search (default: 0)
    """
    driver = PyclingoDriver()
    if "asp" in dump:
        driver.out = sys.stdout

    for path in [binary, library]:
        if not os.path.exists(path):
            sys.exit("%s does not exist." % path)

    # Create the parser, and generate the corpus
    parser = ABIParser()
    corpusA = parser.get_corpus_from_elf(binary)
    corpusB = parser.get_corpus_from_elf(library)
    setup = ABICompatSolverSetup()
    return driver.solve(setup, corpusA, corpusB, dump, models, timers, stats, tests)
