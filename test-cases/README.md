# Test Cases

This is start of a folder where we can define (and run) test cases. A test case means:

1. We've identified something we want to call an ABI conflict or incompatibility.
2. We write a dummy example for it, in c and cpp (arguably we need more but let's start reasonably).
3. We then compare results using abicompat, and whatever our method is, across a bunch of different compilers.

To develop locally, I'll just use the small set of compilers that I have. But
we will eventually move this to where there are more and we can test across them all.
The test examples will not just allow us to compare output / results, but also 
let us run gdb to better understand what is going on (I haven't been able to do
this yet).


## Test Cases to Add

This is a short list that I'm putting together from the work in [abi-python](../abi-python).

0. **the environment has not changed**: This is an environment, as defined by libabigail.
1. **A known needed symbol is undefined**: A symbol that is undefined in our main binary, and defined in the one that works, but not defined in the one we are comparing is a known needed symbol that is undefined.
2. **The architecture do not match**: If the architectures do not match between the corpora, this is not compatible (we probably could compare either the libraries or the new library and the binary).
3. **The sonames do not match**: if the sonames do not match (for either set) then they are not compatible. In practice my test library did not have one.
4. **functions have the same length and order of parameters**: At least to start, we can say functions should have the same number of parameters, and if we compare the order, they are the same. In practice I don't know if this always has to hold true. We can call these parameters (in the same order of the same function) matching.
5. **function matching parameters must have the same type and size**: Once we find a set of matching parameters, they need to have the same type and size.
6. **parameters cannot be missing**: This is related to #4 because if a parameter is missing, the lengths would be different. But in practice, some of the compilers don't seem to be able to provide debug information for parameters, so they come across as missing. We need to be able to determine whether something is truly missing, or the compiler just decided to not include it.
7. **arrays are the same if the elements are of the same type**: but this says nothing about their size. We will want a test case of different sizes to see what libabigail does.
8. **references or pointers are the same if the thing they point to / the underlying types are the same**
9. **enums are the same if we can match the entries 1:1 and they have the same type**: And we need to think about what happens if they have different lengths.
10. **class types are the same if all of their base specifiers are the same**
11. **class types are the same if all of their data members are the same**
11. **class types are the same if all of their virtual member functions are the same**
12. **class types are the same if all of their member function templates are the same**
13. **union type declarations are the same if their non static data members are the same**
14. **scopes are the same if their member declarations are the same**
15. **Function declarations are the same if their types are the same**
16. **Typedef declarations are the same if their underlying types are the same**
17. **Translation units are the same if their global scopes are the same**

## Getting Started

First build the container, which has both libabigail and gdb.

```bash
$ docker build -t abigail .
```

Then shell into the image, binding the present working directory.

```bash
$ docker run --rm -it -v $PWD/:/code abigail bash
```

Then you can navigate to an example (and run make if you haven't built the libraries
yet)

```bash
cd examples/array_size_change/cpp
```

And for now, we can run abicompat.

```bash
$ # abicompat math-client libmath-v1.so  libmath-v2.so 
root@01fec8283fad:/code/examples/array_size_change/cpp# echo $?
0
```

Eventually we will have a whole suite of tests, and run each against abicompat
and our custom tool.

## gdb

Here are instructions from Matt that I'll use for gdb, when the time comes.

```
First: build libagigail with debug and no optimizations.
On configure line: ‘CXXFLAGS=-O0 -g’ and ‘CFLAGS=-O0 -g’
Get test program
Run abicompat in gdb:
      % gdb abicompat
(gdb) break compute_diff  #add breakpoint at compute_diff function
(gdb) run [command line args to abicompat]
… GDB tells you it hit a breakpoint at compute diff…
(gdb) backtrace         #print call stack
(gdb) c                         #continue to next instance
(gdb) p <some variable name> #print the value of a variable
```
