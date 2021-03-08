# abicompat

The source code for abicompat is [abicompat.cc](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc).
There is a tiny bit of documentation in the header, but I'd like to read through
the script and try to figure out what is going on. As a summary from the header of
the file:

>> This program reads a program A, one library L in version V which A links against, and the same library L in a different version, V+P. The program then checks that A is still ABI compatible with L in version V+P.

In simpler terms, if I compile A with L version 1.0, I want to check if L 2.0 is also compatible. That
means that the expected usage is to provide an application and two libraries. The
less likely use case is what is called "weak mode" meaning that just a single
application and single library are provided, and we check if they are compatible.
Compatible means that the types of variables and functions provided by the library
are what the application expects.

 - [An example command](#an-example-command)
 - [The command line parser](#the-command-line-parser)
 - [Program execution](#execution)

## An example command

For this exercise, we will
walk through the simplest example of comparing if two libraries are compatible
as described [here](https://sourceware.org/libabigail/manual/abicompat.html):

```bash
$ abicompat test-app libtest-0.so libtest-1.so
```

For the above, we will call our compiled app binary `app`, and the two libraries
`lib0` and `lib1`. The premise is that we've compiled `app` already with `lib0`,
and we want to use abicompat to determine if `lib1` is also compatible.

## The Command Line Parser

The script provides a good number of options for customizing behavior. You might
be interested to read about these to better understand inputs (and this the application
flow) The main ones of interest include  (but are not limited to):

### --list-undefined-symbols

> display the list of undefined symbols of the application

This actually translates in practice to _only_ list the undefined symbols. This
might be useful to figure out what symbols are missing (to be found elsewhere?)

### --show-base-names

> in the report, only show the base names of the files; not the full paths

This is fairly straight forward. It likely simplifies the visual output, if you
can visually parse it without needing full paths.

### --app-debug-info-dir

> set the path to the debug information directory for the application

I was looking this up, and it looks like [according to this documentation](https://sourceware.org/gdb/onlinedocs/gdb/Separate-Debug-Files.html)
that debug information can be larger than the binary itself, so programs often write it to
separate files or folders. I suspect a lot of information that we need for ABI would
be written here. It also [looks like](https://bugs.eclipse.org/bugs/show_bug.cgi?id=376725) it's common that programs are compiled 
without debug information, which would be the `-g` gcc option. Also according to that source,
you can look for debug information with:
 
```bash
$ objdump -h -j .debug_info
```

For example, I tried this on a library compiled with `g++ -g`:

```bash
$ objdump -h -j .debug_info ./libtest-v0.so 

./libtest-v0.so:     file format elf64-x86-64

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
 22 .debug_info   0000007f  0000000000000000  0000000000000000  0000307a  2**0
                  CONTENTS, READONLY, DEBUGGING, OCTETS
```

There is is! And then without the `-g`, I don't see it:

```bash
$ objdump -h -j .debug_info ./libtest-v0.so 

./libtest-v0.so:     file format elf64-x86-64

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
objdump: section '.debug_info' mentioned in a -j option, but not found in any input file
```

### --lib-debug-info-dir1

> set the path to the debug information directory for the first library

This would be the same debug information, but for the first library instead of the
application in question.

### --lib-debug-info-dir2

> set the path to the debug information directory for the second library

This argument speaks for itself! It's the same as the previous argument, but
for the second library.

### --suppressions

> specify a suppression file

Libabigail supports these [suppression files](https://sourceware.org/libabigail/manual/libabigail-concepts.html#suppr-spec-label)
that make it easier to suppress different kinds of output when you use the tool. For example, if we
find that a subset of output isn't important for what we want to do, we would write a custom suppression file
to do exactly that.

### --no-redundant

> do not display redundant changes

I found this better described in [another executable's documentation](https://sourceware.org/libabigail/manual/abidiff.html) -
 "A redundant change is a change that has been displayed elsewhere in the report." In practice, I suspect this just means showing
 the same information twice? For `abidw` that doesn't have this flag, I remember a particular entry being displayed twice, but
I'm not sure if that's a comparable case.

### --no-show-locs

> do not show location information

I suspect this means that we would get the output, and not see where the change is (e.g., the offset or line).

### --redundant

> display redundant changes (this is the default)

I'm not sure why this is a flag if it's the default, and if we have a flag to change it (`--no-redundant`)
as described above. What is the use case for this flag?

### --weak-mode

> check compatibility between the application and just one version of the library.

As this is described in the documentation, only one version of the library is required:

```bash
$ abicompat --weak-mode <the-application> <the-library>
```

> In this weak mode, the types of functions and variables exported by the library and consumed by the application (as in, the symbols of the these functions and variables are undefined in the application and are defined and exported by the library) are compared to the version of these types as expected by the application. And if these two versions of types are different, abicompat tells the user what the differences are.
> In other words, in this mode, abicompat checks that the types of the functions and variables exported by the library mean the same thing as what the application expects, as far as the ABI is concerned.
> Note that in this mode, abicompat doesn’t detect exported functions or variables (symbols) that are expected by the application but that are removed from the library. That is why it is called weak mode.

I tried this on a binary and library that helped generated it, and there was no output
and return code 0, which indicates that they are equal (I think).

## Execution

I'll walk through the steps and add snippets of code, if they are helpful.
The program starts at [main](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L604)
as you would expect.

### 1. Preparing paths for elfutils

We are first [parsing command line arguments](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L118), which
have been noted above. Most of them are what you would expect (or just boring) - setting booleans and paths
to files. The one interesting note is that it looks like we are going to
use [elfutils](https://sourceware.org/elfutils/) to read the debug information.

```cpp
// elfutils wants the root path to the debug info to be
// absolute.
opts.lib1_di_root_path =
   abigail::tools_utils::make_path_absolute(argv[i + 1]);
++i;
```

as the tool wants an absolute path and not a relative one. At the time of writing, 
you can find this snippet [here](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L166).
We cut out early if the user asks for a version, for help, or provides an unrecognized argument.

####  What is elfutils?

> elfutils is a collection of utilities and libraries to read, create and modify ELF binary files, find and handle DWARF debug data, symbols, thread state and stacktraces for processes and core files on GNU/Linux. 

This makes sense, because the ABI corpus have both `elf-function-symbols` and `elf-variable-symbols`.


### 2. Input ELF Validation

We check if the input files exist, and are [regular files](https://github.com/woodard/libabigail/blob/master/src/abg-tools-utils.cc#L732).
We also read a 264 length buffer to determine the [file type](https://github.com/woodard/libabigail/blob/master/src/abg-tools-utils.cc#L1366),
which must be ELF. If it's not, we exit with an error. The cool part about this is that you can literally look at the first
line of a (mostly) jiggerishy binary, and you see...

```
^?ELF^B^A^A^@^@^@^@
```

And indeed that's what we are looking for in the C++ code!

```cpp
if (buf[0] == 0x7f
    && buf[1] == 'E'
    && buf[2] == 'L'
    && buf[3] == 'F')
  return FILE_TYPE_ELF;
```

And then we basically say "YOU SHALL NOT PASS!" if it's not an ELF:

```cpp
if (type != abigail::tools_utils::FILE_TYPE_ELF)
  {
    emit_prefix(argv[0], cerr)
      << opts.app_path << " is not an ELF file\n";
    return abigail::tools_utils::ABIDIFF_ERROR;
  }
```

### 3. Suppression Files

At this point, we can exit early if the libraries and application in question
are in the suppressed list:

```cpp
bool files_suppressed = (file_is_suppressed(opts.app_path, supprs)
		   || file_is_suppressed(opts.lib1_path, supprs)
		   ||file_is_suppressed(opts.lib2_path, supprs));

if (files_suppressed)
  // We don't have to compare anything because a user
  // suppression specification file instructs us to avoid
  // loading either one of the input files.
  return abigail::tools_utils::ABIDIFF_OK;
```
I'm not totally sure why a user would call a function to compare two files that
are in their suppressed list. I can only guess this tool might be used somewhere
in an automated fashion, comparing all pairs of files (but ignoring some special few).

### 4. Read corpus from elf

We now read the corpus from the applcation ELF file! This is done [here](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L669).

```cpp
char * app_di_root = opts.app_di_root_path.get();
vector<char**> app_di_roots;
app_di_roots.push_back(&app_di_root);
status status = abigail::dwarf_reader::STATUS_UNKNOWN;
environment_sptr env(new environment);
corpus_sptr app_corpus = read_corpus_from_elf(opts.app_path,
			 app_di_roots, env.get(),
			 /*load_all_types=*/opts.weak_mode,
			 status);
```

#### Creating a Read Context

The way that this works seems to be to create what's called a [read context]()
and then pass this read context around to all the routines that need specific dwarf bits.
The library notes:

> When a new data member is added to this context, it must be initiliazed by the read_context::initiliaze() function.  So please do not forget.

The creation of the read context looks like this:

```cpp
read_context_sptr
create_read_context(const std::string&		elf_path,
		    const vector<char**>&	debug_info_root_paths,
		    ir::environment*		environment,
		    bool			load_all_types,
		    bool			linux_kernel_mode)
{
  // Create a DWARF Front End Library handle to be used by functions
  // of that library.
  read_context_sptr result(new read_context(elf_path, debug_info_root_paths,
					    environment, load_all_types,
					    linux_kernel_mode));
  return result;
}
```

If we look closer at this new [read_context](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L2293)
it's calling an initialize function 

```cpp
  read_context(const string&	elf_path,
	       const vector<char**>& debug_info_root_paths,
	       ir::environment* environment,
	       bool		load_all_types,
	       bool		linux_kernel_mode)
  {
    initialize(elf_path, debug_info_root_paths, environment,
	       load_all_types, linux_kernel_mode);
  }
```

"Environment" is a pretty loaded term and it's not clear what it's referencing. Here
is what the function header says:

> @param environment the environment used by the current context.
> This environment contains resources needed by the reader and by
> the types and declarations that are to be created later.  Note
> that ABI artifacts that are to be compared all need to be
> created within the same environment.

The start of the function has a lot of data structures that are essentiall reset 
or emptied, and this makes sense if we are making a new read context. For example:

```cpp
supprs_.clear();
decl_die_repr_die_offsets_maps_.clear();
type_die_repr_die_offsets_maps_.clear();
die_qualified_name_maps_.clear();
...
```

We also clear what is called "translation unit data"

```cpp
/// Clear the data that is relevant only for the current translation
/// unit being read.  The rest of the data is relevant for the
/// entire ABI corpus.
void
clear_per_translation_unit_data()
{
  while (!scope_stack().empty())
    scope_stack().pop();
  var_decls_to_re_add_to_tree().clear();
  per_tu_repr_to_fn_type_maps().clear();
}
```

It then looks like (after clearing everything) we create this read context
as follows:

```cpp
memset(&offline_callbacks_, 0, sizeof(offline_callbacks_));
create_default_dwfl(debug_info_root_paths);
options_.env = environment;
options_.load_in_linux_kernel_mode = linux_kernel_mode;
options_.load_all_types = load_all_types;
drop_undefined_syms_ = false;
load_in_linux_kernel_mode(linux_kernel_mode);
```
I think [memset](http://www.cplusplus.com/reference/cstring/memset/) is 
setting the start of our reader to the first position. The function `create_default_dwfl`
I think means "create default dwarf file reader" and this is where we actually use the
elfutils functions [dwfl_begin](https://github.com/ganboing/elfutils/blob/master/libdwfl/dwfl_begin.c)
to "set up a session using libdwfl."

```cpp
void
create_default_dwfl(const vector<char**>& debug_info_root_paths)
{
  offline_callbacks()->find_debuginfo = dwfl_standard_find_debuginfo;
  offline_callbacks()->section_address = dwfl_offline_section_address;
  offline_callbacks()->debuginfo_path =
    debug_info_root_paths.empty() ? 0 : debug_info_root_paths.front();
    handle_.reset(dwfl_begin(offline_callbacks()),
		  dwfl_deleter());
  debug_info_root_paths_ = debug_info_root_paths;
}
```

My best guess is that this function returns a loaded elf, where the reader is
at position 0 and ready to jump around and find data.

#### Reading the corpus, debugging info

We then jump back to [this function](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L17325)
which is called by the one with the same name (mentioned above) that accepts a path. This one accepts
the read context that we just made. This [loads debug info](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L2680)
using another function provided by [elfutils](https://github.com/cuviper/elfutils/blob/08ed26703d658b7ae57ab60b865d05c1cde777e3/libdwfl/offline.c#L298) which looks like it comes down to seeking to the right spot and reading. We finish with [dwfl_report_end](https://github.com/cuviper/elfutils/blob/08ed26703d658b7ae57ab60b865d05c1cde777e3/libdwfl/dwfl_module.c#L210) which I think basically resets that
particular read. It looks like these files can have multiple debugging roots, and we look for them [here](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L2699)

#### Reading the corpus, elf symbols

We then call a function defined for the context to "load_elf_properties"

```cpp
ctxt.load_elf_properties();  // DT_SONAME, DT_NEEDED, architecture
```

This function is defined [here](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L7190)
and comes down to loading the architecture and "soname" and "needed."

```cpp
/// Load various ELF data.
///
/// This function loads ELF data that are not symbol maps or debug
/// info.  That is, things like various tags, elf architecture and
/// so on.
void
load_elf_properties()
{
  load_dt_soname_and_needed();
  load_elf_architecture();
}
```
I think "soname" refers verbatim to "the name of the so (or library)." [[ref](https://en.wikipedia.org/wiki/Soname)].

```bash
$ objdump -p libx.so.1.3 | grep SONAME
  SONAME     libx.so.1
```

For each of these functions [load_dt_soname_and_needed](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L7165)
and [load_elf_architecture](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L7179) it looks like we use
[a function to walk through the dynamic sections](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L1443)
to search for a tag of interest, and then there is a function provided by elfutils to get a header directly, used as follows:

```cpp
GElf_Ehdr eh_mem;
GElf_Ehdr* elf_header = gelf_getehdr(elf_handle(), &eh_mem);
```
The function is defined [here](https://github.com/ganboing/elfutils/blob/760925bc7b43814d30ee4e0396709fe8a3f66cd6/libelf/gelf_getehdr.c#L96)
in elfutils and seems to lock the file, read and return the header at the destination.


#### Reading the corpus, symbol table

It looks like the [symbol table](https://refspecs.linuxbase.org/elf/gabi4+/ch4.symtab.html) 

> An object file's symbol table holds information needed to locate and relocate a program's symbolic definitions and references. A

has global variable and symbol addresses, and this
is also where it tells us what is undefined. We next read this table (if a boolean is indicated
that we want to, which defaults to true) and call the function [load_symbol_maps](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L7083). This function calls [load_symbol_maps_from_symtab_section](https://github.com/woodard/libabigail/blob/master/src/abg-dwarf-reader.cc#L6171) and takes a similar approach to using a library from elfutils, but this one is called
[gelf_getshhdr](https://github.com/ganboing/elfutils/blob/760925bc7b43814d30ee4e0396709fe8a3f66cd6/libelf/gelf_getshdr.c#L40)
which specifically is going to return a "section header" instead of the elf header.

If we find no debug info, no sumbol table, then we cut out early. This must be the meat of an ABI
comparison.

```cpp
if (// If no elf symbol was found ...
  status & STATUS_NO_SYMBOLS_FOUND
      // ... or if debug info was found but not the required alternate
      // debug info ...
      || ((status & STATUS_ALT_DEBUG_INFO_NOT_FOUND)
	  && !(status & STATUS_DEBUG_INFO_NOT_FOUND)))
// ... then we cannot handle the binary.
return corpus_sptr();
```

#### Read the debug info into the corpus

We then read variable and function descriptions via the dwarf handle:

```cpp
// Read the variable and function descriptions from the debug info
// we have, through the dwfl handle.
corpus_sptr corp = read_debug_info_into_corpus(ctxt);
```

**stopped here, work in progress**!
