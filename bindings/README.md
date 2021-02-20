# Libabigail Python

This is an attempt to create python bindings for [Libabigail](https://sourceware.org/git/?p=libabigail.git;a=tree).
We will develop within a [Dockerfile](Dockerfile).

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
$ docker run -it --rm -v $PWD/src:/code/src libab-python bash
```

## Figuring out Signatures

It looks like we can do the following to find the function signatures to call (below
we see the unmangled ones):

```bash
$ nm -D /usr/local/lib/libabigail.so

                 U __assert_fail
                 U __cxa_allocate_exception
                 U __cxa_atexit
                 U __cxa_bad_cast
                 U __cxa_bad_typeid
                 U __cxa_begin_catch
                 U __cxa_demangle
                 U __cxa_end_catch
                 w __cxa_finalize
                 U __cxa_guard_abort
                 U __cxa_guard_acquire
                 U __cxa_guard_release
                 U __cxa_pure_virtual
                 U __cxa_rethrow
                 U __cxa_throw
                 U __dynamic_cast
                 U __errno_location
                 U __fxstat
                 w __gmon_start__
                 U __gxx_personality_v0
                 U __lxstat
                 w __pthread_key_create
                 U __stack_chk_fail
                 U __tls_get_addr
                 U __xpg_basename
                 U __xstat
00000000002e5980 T abigail_get_library_version
                 U abort
                 U close
                 U closedir
                 U dirname
                 U dwarf_attr
                 U dwarf_attr_integrate
                 U dwarf_begin
                 U dwarf_child
                 U dwarf_cu_die
                 U dwarf_cu_getdwarf
                 U dwarf_decl_file
                 U dwarf_diecu
                 U dwarf_dieoffset
                 U dwarf_end
                 U dwarf_formaddr
                 U dwarf_formflag
                 U dwarf_formref_die
                 U dwarf_formsdata
                 U dwarf_formstring
                 U dwarf_formudata
                 U dwarf_getalt
                 U dwarf_getelf
                 U dwarf_getlocation
                 U dwarf_next_unit
                 U dwarf_offdie
                 U dwarf_offdie_types
                 U dwarf_ranges
                 U dwarf_setalt
                 U dwarf_siblingof
                 U dwarf_tag
                 U dwfl_begin
                 U dwfl_end
                 U dwfl_module_getdwarf
                 U dwfl_module_getelf
                 U dwfl_offline_section_address
                 U dwfl_report_end
                 U dwfl_report_offline
                 U dwfl_standard_find_debuginfo
                 U elf_begin
                 U elf_end
                 U elf_getdata
                 U elf_getphdrnum
                 U elf_getscn
                 U elf_getshdrstrndx
                 U elf_gnu_hash
                 U elf_hash
                 U elf_ndxscn
                 U elf_nextscn
                 U elf_rawdata
                 U elf_strptr
                 U elf_version
                 U fgets
                 U free
                 U fts_close
                 U fts_open
                 U fts_read
                 U fts_set
                 U gelf_fsize
                 U gelf_getdyn
                 U gelf_getehdr
                 U gelf_getphdr
                 U gelf_getrel
                 U gelf_getrela
                 U gelf_getshdr
                 U gelf_getsym
                 U gelf_getverdaux
                 U gelf_getverdef
                 U gelf_getvernaux
                 U gelf_getverneed
                 U gelf_getversym
                 U gelf_offscn
                 U get_current_dir_name
                 U getenv
                 U gettimeofday
                 U isalnum
                 U isspace
                 U memchr
                 U memcmp
                 U memcpy
                 U memmove
                 U memset
                 U mkstemp
                 U open
                 U opendir
                 U pclose
                 U popen
                 U pthread_cond_broadcast
                 U pthread_cond_signal
                 U pthread_cond_wait
                 U pthread_create
                 U pthread_join
                 U pthread_mutex_lock
                 U pthread_mutex_unlock
                 U rand
                 U readdir
                 U realpath
                 U regcomp
                 U regexec
                 U regfree
                 U remove
                 U srand
                 U strcmp
                 U strdup
                 U strlen
                 U strstr
                 U strtol
                 U strtoll
                 U strtoull
                 U sysconf
                 U system
                 U time
                 U xmlFree
                 U xmlFreeTextReader
                 U xmlGetProp
                 U xmlNewTextReaderFilename
                 U xmlReaderForIO
                 U xmlReaderForMemory
                 U xmlStrEqual
                 U xmlTextReaderExpand
                 U xmlTextReaderGetAttribute
                 U xmlTextReaderName
                 U xmlTextReaderNext
                 U xmlTextReaderNodeType
                 U xmlTextReaderRead
```

## Testing ctypes

It was recommended to me to try ctypes first, so let's shell into the container (above)
and then try a simple python script to import the library (note that ipython is installed
so you can open a terminal with `ipython`):

```python
import ctypes

# Load the shared library into c types.
libab = ctypes.CDLL("/usr/local/lib/libabigail.so")
```

Let's try getting the current directory name (which shouldn't take any argumets). If
we just run the function, it looks like we get the wrong output type.

```python
libab.get_current_dir_name()
39281152
```

I think we need to tell it to return a string type?

```python
libab.get_current_dir_name.restype = ctypes.string_at
In libab.get_current_dir_name()
b'/code'
```

This is progress! I think before moving forward we need to have a better direction
about what specifically we want to do. It's not clear that ctypes is the best
choice since it doesn't easily handle templates. There is a nice [post here](https://realpython.com/python-bindings-overview/)
that reviews several libraries for making said documentation.

1. Figure out the functions that we need
2. Try creating a function that can specify the correct types
3. Try running the function and getting output in Python
