# Compute Diffs

The file [rules.md](rules.md) goes through the high level comparison of libabigail
and glibc, but really most of the logic that we need is in the Compute Diffs functions,
which I can inspect for each type. This will be the goal of this file. Other than
matching symbols, I'm not sure about how else we decide to compare two things.
Let's assume we know that.

## Compute Diff for Declarations (decls)

- [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3075)

This function calls three "sub functions" for compute_diff, for each
of:

 - function declarations
 - variable declarations
 - distinct kinds

```cpp
 ((d = try_to_diff<function_decl>(first, second, ctxt))
   || (d = try_to_diff<var_decl>(first, second, ctxt))
   || (d = try_to_diff_distinct_kinds(first, second, ctxt)));
```
 
All discussed next.

## Compute Diff for Distinct Kinds

- [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2750)

It looks like the logic here falls back to [this function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2599),
where we call them different if they are distinct kinds:

```cpp
  if (!!first != !!second)
    return true;
  if (!first && !second)
    // We do consider diffs of two empty decls as a diff of distinct
    // kinds, for now.
    return true;
  if (first == second)
    return false;

  const type_or_decl_base &f = *first, &s = *second;
  return typeid(f) != typeid(s);
}
```

Explanation for [!! is here](http://www.cplusplus.com/forum/beginner/4844/). I think this
says:

 - they are distinct kinds (not compatible) if their null types are different
 - they are distinct kinds (not compatible) if both are empty
 - they are distinct kinds (not compatible) if the type ids are different

For the facts we are generating, I think we would be checking

## Compute Diff for Function Declaration

**TODO**

## Compute Diff for Variable  Declaration

**TODO**

TODO:

1. Finish deriving this entire list
2. Come up with dummy tests for each
3. Run for each of libabigail and our tool
