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

This is a short list that I'm putting together from the work in [abi-python](../abi-python) and [this guide](https://community.kde.org/Policies/Binary_Compatibility_Issues_With_C++). For the latter, I'll add `[kde]` after each point that is derived from the guide. I'm not sure the organization is correct, but we can move things around.

### Environment and Host

**the environment has not changed**
This is an environment, as defined by libabigail.

**The architecture do not match**
If the architectures do not match between the corpora, this is not compatible (we probably could compare either the libraries or the new library and the binary).

**The sonames do not match**
if the sonames do not match (for either set) then they are not compatible. In practice my test library did not have one.

### Symbols

**A known needed symbol is undefined**: A symbol that is undefined in our main binary, and defined in the one that works, but not defined in the one we are comparing is a known needed symbol that is undefined.

**Extend reserved bit fields so that the bit field crosses the boundary of its underlying type (8 bits for char & bool, 16 bits for short, 32 bits for int, etc.)** `kde`

### Functions

**functions have the same length and order of parameters**

At least to start, we can say functions should have the same number of parameters, and if we compare the order, they are the same. In practice I don't know if this always has to hold true. We can call these parameters (in the same order of the same function) matching.

**function matching parameters must have the same type and size**

Once we find a set of matching parameters, they need to have the same type and size.

**parameters cannot be missing**

This is related to #4 because if a parameter is missing, the lengths would be different. But in practice, some of the compilers don't seem to be able to provide debug information for parameters, so they come across as missing. We need to be able to determine whether something is truly missing, or the compiler just decided to not include it.

**Function declarations are the same if their types are the same**

**A private non-virtual function is removed that is called by an inline function** `kde`

**Private static members are removed that are called by any inline functions** `kde`

**un-export an existing function** `kde`

**remove an existing function** `kde`

"Remove the implementation of existing declared functions. The symbol comes from the implementation of the function, so this is effectively the function."

**Inline it**

"Includes moving a member function's body to the class definition, even without the inline keyword."
[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Inline_a_function).

**changing the access rights to a function** `kde`

E.g., public to private. [example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_access_rights)

**changing the CV qualifiers of a member function** `kde`

[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_CV-qualifiers_of_a_member_function)

**extending a function to have a new parameter, even if there is a default value** `kde`

**changing the [return type](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_return_type) in any way** `kde`

"Exception: non-member functions declared with extern "C" can change parameter types (be very careful)."

### Virtual Member Functions

**add a virtural function to a class that doesn't have any virtual functions or bases** `kde`

[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Add_a_virtual_member_function_to_a_class_without_any)

**add new virtual functions to non-leaf classes** `kde`

[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Add_new_virtuals_to_a_non-leaf_class)
This breaks subclasses. "Note that a class designed to be sub-classed by applications is always a non-leaf class."

**change the order of virtual functions in the class declaration** `kde`

[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_order_of_the_declaration_of_virtual_functions)

**override an existing virtual function if the overriding function has a covariant return type for which the more-derived type has a pointer address different from the less-derived one** `kde` 

"This usually happens when, between the less-derived and the more-derived ones, there's multiple inheritance or virtual inheritance."

[example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Override_a_virtual_that_doesn.27t_come_from_a_primary_base)

**Remove a virtual function, even if it is a reimplementation of a virtual function from the base class** `kde`

**For static non-private members or for non-static non-member public data** `kde`

 - Remove or unexport it
 - Change its [type](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_type_of_global_data)
 - Change its [CV-qualifiers](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_CV-qualifiers_of_global_data)

**For non-static members**: `kde`

- add new data members to an existing class.
- change the order of non-static data members in a class.
- change the type of the member, except for signedness (or more generally if the types are guaranteed to have the same size, and the member is not used by any inline method)
- remove existing non-static data members from an existing class.

### Arrays

**arrays are the same if the elements are of the same type**
but this says nothing about their size. We will want a test case of different sizes to see what libabigail does.

### Pointers
**references or pointers are the same if the thing they point to / the underlying types are the same**

### Enums
**enums are the same if we can match the entries 1:1 and they have the same type**

And we need to think about what happens if they have different lengths.

**new enums can be appended to existing ones only if the compiler does not choose a larger underlying type** `kde`

> Compilers have some leeway to choose the underlying type, so from an API-design perspective it's recommended to add a Max.... enumerator with an explicit large value (=255, =1<<15, etc) to create an interval of numeric enumerator values that is guaranteed to fit into the chosen underlying type, whatever that may be.

### Classes

**class types are the same if all of their base specifiers are the same**
**class types are the same if all of their data members are the same**
**class types are the same if all of their virtual member functions are the same**
**class types are the same if all of their member function templates are the same**

**a base function of a class is overridden and the overriding function has a covariant return type** `kde`

"It's only a binary-compatible change if the more-derived type has always the same pointer address as the less-derived one. If in doubt, do not override with a [covariant return type](http://en.wikipedia.org/wiki/Covariant_return_type)."

**unexport or remove a class** `kde` see [example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Unexport_or_remove_a_class)

**change the class hierarchy in any way** `kde` [example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_class_hierarchy)

E.g., add, remove, or reorder base classes

### Templates

**change the template arguments in any way** `kde`

E.g., add, remove, or re-order, [example](https://community.kde.org/Policies/Binary_Compatibility_Examples#Change_the_template_arguments_of_a_template_class)

### Union Types

**union type declarations are the same if their non static data members are the same**

### Scopes

**scopes are the same if their member declarations are the same**

### Type defs

**Typedef declarations are the same if their underlying types are the same**


### Translation Units

**Translation units are the same if their global scopes are the same**

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
