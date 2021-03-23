# Rules

These rules are derived from tracing [corpus_diff](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L11031). I will include questions along the way. [Current issues](#issues) with links are provided at the end.

## The Input

Let's start with the input. We have:

### a diff context

A [diff context](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L261)
holds booleans that tell the `corpus_diff` function in libabigail what is important to look at. This is nice because it gives us some
hints about what is being inspected. We will likely encounter these booleans as we compute the diff.

```cpp
static diff_context_sptr
create_diff_context(const options& opts)
{
  diff_context_sptr ctxt(new diff_context());

  ctxt->show_added_fns(false);
  ctxt->show_added_vars(false);
  ctxt->show_added_symbols_unreferenced_by_debug_info(false);
  ctxt->show_linkage_names(true);
  ctxt->show_redundant_changes(opts.show_redundant);
  ctxt->show_locs(opts.show_locs);
  ctxt->switch_categories_off
    (abigail::comparison::ACCESS_CHANGE_CATEGORY
     | abigail::comparison::COMPATIBLE_TYPE_CHANGE_CATEGORY
     | abigail::comparison::HARMLESS_DECL_NAME_CHANGE_CATEGORY
     | abigail::comparison::NON_VIRT_MEM_FUN_CHANGE_CATEGORY
     | abigail::comparison::STATIC_DATA_MEMBER_CHANGE_CATEGORY
     | abigail::comparison::HARMLESS_ENUM_CHANGE_CATEGORY
     | abigail::comparison::HARMLESS_SYMBOL_ALIAS_CHANGE_CATEGORY);

  // Load suppression specifications, if there are any.
  suppressions_type supprs;
  for (vector<string>::const_iterator i = opts.suppression_paths.begin();
       i != opts.suppression_paths.end();
       ++i)
    if (check_file(*i, cerr, opts.prog_name))
      read_suppressions(*i, supprs);

  if (!supprs.empty())
    ctxt->add_suppressions(supprs);

  return ctxt;
}
```

### corpus readers

You can see in [abicompat](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L781)
described in [this exercise](../../abicompat) that we read in two corpora and a binary. Specifically, the "normal" mode means that
we have:

1. a binary of interest (app_corpus)
2. a library known to work with it, meaning it was linked and worked (lib1_corpus)
3. a second library we are assessing (lib2_corpus)

For the purposes of this exercise, we will be walking through this "normal" mode with three
different objects. From the link above, that looks like this:

```cpp
    s = perform_compat_check_in_normal_mode(opts, ctxt,
					    app_corpus,
					    lib1_corpus,
					    lib2_corpus);
```

The ctxt refers to the diff context described above. We then jump up to
[this function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L314)
in the same file, and we can start deriving rules from this point.

## Rules

The following sections will
have to kinds of headings:

 - **rules**: are explicit comparisons or rules that can be applied as a requirement for ABI compatability
 - **steps**: are intermediate rules needed to prepare data for a rule.



### Rule 1: We must have corpora

This is obvious, but both libraries and the corpora for the main binary [must be defined](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L320):


```cpp
  ABG_ASSERT(lib1_corpus);
  ABG_ASSERT(lib2_corpus);
  ABG_ASSERT(app_corpus);
```

If any of these don't have debug information, then we cannot get any information about symbols.
I think if one of these assertions fails, we raise an error. [Specifically](https://github.com/woodard/libabigail/blob/1d29610d51280011a5830166026151b1a9a95bba/include/abg-fwd.h#L1417) `ABG_ASSERT` is:

> a wrapper around the 'assert' glibc call.

We will derive
the following rules by walking through the function entry point [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L11031).

### Step after Rule 1: Filter Symbols

Given we have lib1, a library that is known to work, and lib2, a library that we are testing,
and an app, the binary being linked to, we want to:

> compare lib1 and lib2 only by looking at the functions and
> variables which symbols are those undefined in the app.

That means that [in this section](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L329) we:

1. loop through undefined symbols in the app, each has an id string 
2. using the id string, add the id to the end of the vector `get_sym_ids_of_fns_to_keep` for each of lib1 and lib2.
3. do this for function and variable symbols (libabigail separates them but I don't think they need to be).
4. if both function and variable symbols are defined for the corpus, we call [maybe_drop_some_exported_decls](https://github.com/woodard/libabigail/blob/07816b2d59f36be287e397be4f766b588819f2ac/src/abg-corpus.cc#L1567) on the app corpus, which seems to take a bunch of [regular expressions](https://github.com/woodard/libabigail/blob/07816b2d59f36be287e397be4f766b588819f2ac/src/abg-corpus.cc#L85) to determine symbols and functions to keep. 

I haven't yet traced where these regular expressions come from, but knowing that the user can
input lists of suppression files (and looking at the variable names) I'd guess that is a subset. It could be that
we can derive a rule from this filtering, but for now since I don't understand what a user might provide in a suppression file
and why, I'm going to be conservative and say that we don't filter further.

> **Questions**: What do these regular expressions look like, and what is the use case to define them? How often are they defined?  Where do these [other ids](https://github.com/woodard/libabigail/blob/07816b2d59f36be287e397be4f766b588819f2ac/src/abg-corpus.cc#L85) for functions and variables come from?

After this step we [really do the diffing](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/tools/abicompat.cc#L356), which calls [this function](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L3464)
in abg-comparison.cc. Importantly, this "diffing" is happening between lib1_corpus and lib2_corpus, which are derived based on
the undefined symbols in the app. I wish there was a way with libabigail to splot out the undefined symbols in the app
and then show this overlap with each library, but for now we can just assume some subset of symbols undefined in the app
and (possibly) defined in the libraries.


### Rule 2: Consider dependencies too

Libabigail doesn't currently do this, but there are other library dependencies "elf needed" listed in the binary.
[This bug](https://sourceware.org/bugzilla/show_bug.cgi?id=27514) points this out. If we (in spack) can totally
derive this entire list of dependencies, it would be more comprehensive to be able to load symbols across all libraries and be
absolutely sure that everything matches (as opposed to just looking at undefined symbols in the app, which is
what libabigail does). [This bug](https://sourceware.org/bugzilla/show_bug.cgi?id=27208) is in the same thread.


### Rule 2: Corpora must be derived in the same environment

The libabigail library has a concept of an [environment](https://github.com/woodard/libabigail/commit/b2e5366d3f0819507006b4369f1fcc0aa93ca283), and [they must be equal](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L11046) to do a comparison. The description of the linked commit doesn't really clarify what an environment is beyond resoures and:

> An environment is a place where one can put resources that need to live longer than all the other artifacts of the Abigail system.  And so, the code that creates Abigail artifacts needs and environment of for said artifacts to use.  In other words, artifacts now use an environment.

and

> An environment can be seen as the boundaries in which all related Abigail artifacts live.

I don't totally understand this concept (and how we would translate it to spack) but the
class is [defined here](https://github.com/woodard/libabigail/blob/07816b2d59f36be287e397be4f766b588819f2ac/include/abg-ir.h#L124).
It seems to hold information about different types, so maybe types can change between different
comparisons of ABI. This will need to be a rule, but I'm not sure how it is represented in the context of spack.

At this point we create a [corpus diff](https://github.com/woodard/libabigail/blob/1d29610d51280011a5830166026151b1a9a95bba/include/abg-comparison.h#L492) [here](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L11051) with the two 
corpora (the 

### Rule 3. Sonames and architecutres must be equal.

We can see these two lines [here](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L11055). Each
library corpus has a function to get the soname and architecture, and we save to variables:

```cpp
  r->priv_->sonames_equal_ = f->get_soname() == s->get_soname();

  r->priv_->architectures_equal_ =
    f->get_architecture_name() == s->get_architecture_name();
```
and [later on](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L9996) this is output as a warning message (I assume this means not compatible in most cases. It's printed to the screen to show the user).

```cpp
  if (!sonames_equal_)
    out << indent << "ELF SONAME changed\n";

  if (!architectures_equal_)
    out << indent << "ELF architecture changed\n";
```

### Steps to prepare for Calculate Diff

#### 1. populating diff context

At this point, we jump into a sequence of calls [here](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L11060)
to use the function `calculate_diff` with several different kinds of inputs. We can use [ctags](https://ctags.io/) to easily jump around
to find the right function. It actually looks like we use the same function that is overloaded (is that the correct term?) to be able to accept different kinds of arguments, meaning we call what looks like the same function, but provide different vectors of things and types, namely:

 - publicly defined and exported functions
 - publicly defined and exported variables
 - function elf symbols not referenced by debug info
 - variable elf symbols not referenced by debug info
 - types not reachable from public functions or global variables that are exported
 
> **Question 1**: why does libabigail split up function and variable symbols?

> **Question 2**: why do we care about un-reachable types (the last bullet?)


We call [this variant](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L3630)
of `compute_diff` on an array of functions, which calls [compute_diff_for_types](https://github.com/woodard/libabigail/blob/master/src/abg-comparison.cc#L2784) providing each of the vectors. I don't understand this fully, but we call a function
that does some [modification of the type](https://github.com/woodard/libabigail/blob/master/src/abg-ir.cc#L8825).
I think what is happening is that we are computing a diff on the types, ultimately calling:

```cpp   
  ((d = try_to_diff<type_decl>(f, s, ctxt))
   ||(d = try_to_diff<enum_type_decl>(f, s, ctxt))
   ||(d = try_to_diff<union_decl>(f, s,ctxt))
   ||(d = try_to_diff<class_decl>(f, s,ctxt))
   ||(d = try_to_diff<pointer_type_def>(f, s, ctxt))
   ||(d = try_to_diff<reference_type_def>(f, s, ctxt))
   ||(d = try_to_diff<array_type_def>(f, s, ctxt))
   ||(d = try_to_diff<qualified_type_def>(f, s, ctxt))
   ||(d = try_to_diff<typedef_decl>(f, s, ctxt))
   ||(d = try_to_diff<function_type>(f, s, ctxt))
   ||(d = try_to_diff_distinct_kinds(f, s, ctxt)));
```

I'd like to talk about each of these "try_to_diff" functions, e.g., [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2691). It looks like we
return a "diff_sptr" (a shared pointer to a diff class). Otherwise we call [this function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3630) that:

 - creates a new [array diff](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3503)
  - which uses a [type_diff_base](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2441)
  - which ultimately create this [diff](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L1850) class.
  

When we provide that result to [initialize canonitcal diff](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L1203) that calls [set_or_get_canonical_diff_for](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L1172) which ultimately (at least I think)
is comparing pointers named "first" and "second" subject [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L1934). I'm having a hard time tracing what is going on here.
There is also a reference to this version of [compute_diff](https://github.com/woodard/libabigail/blob/1d29610d51280011a5830166026151b1a9a95bba/include/abg-diff-utils.h#L1482) that points to using a 
longest common subsequence algorithm to define insertions and deletions. I can't figure out where this gets
called, this entire function and `compute_diff` feels like a hairball to me.

In a larger sense, I think what is happening here is that we pass vectors of different things
to this overloaded `compute_diff` function, and that is going to:

1. get some kind of core type
2. add the diff (the entries and type) to the context, meaning pointer to some first and second objects that we are going to compare later? Compute diff always returns this result, which has updated our diff context:

```cpp
  ctxt->initialize_canonical_diff(result);
  return result;
```

> **Question**: where do [these functions](https://github.com/woodard/libabigail/blob/1d29610d51280011a5830166026151b1a9a95bba/include/abg-diff-utils.h#L1806) get called and what is the context to describe a deletion/insertion?

#### 2. fill lookup tables

In [this function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L8848)
we are looping through deletions and insertions and:

 - adding deleted functions to a lookup, making sure it's not empty and the id is defined.
 - we then do the same kind of looping for insertions, except once we get an id we try to look it up in deleted functions.
 
I don't quite follow the code [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L8896), but it looks like we are checking to see if an added function
is comparable to a deleted function, and if so, we can determine it's a changed function, and add to `changed_fns_map`.

We then:

>  walk the allegedly deleted functions; check if their underlying symbols are deleted as well; otherwise, consider that the function in question hasn't been deleted.

And we do the same for [added functions](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L8925). On a high level I think we are comparing symbol names and versions. It's probably doing
something really simple and feels overly complicated reading it in a language I'm not good at. I wish there were more comments!
It looks like the same logic is copy pasted for [variables](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L9013) instead of functions. At the end we are creating
a lookup with symbol names and symbols, [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L9059) and then [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L9118) for variables. There is one detailed comment about how to consider a new symbol:

> So added_seem has a default version.  If the former corpus had a symbol with the same name as added_sym but with *no* version, then added_sym shouldn't be considered as a newly added symbol.

I'm not sure I'm adding meaningful content at this point, I'm going to assume naively this creates a lookup
table of symbols between the two corpora and it's comparing variables as it goes. It's not clear to me what a difference
/ insertion looks like. It's hard to understand something I can't see.

We jump back [here](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L358) eventually and then
are running sub functions (or whatever you'd call that) on the diff context objects. We can superficially derive rules from that.


### Rule 4. Exported functions and variables were removed

It's considered an [incompatible change](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L10699) if any exported function or variable is removed. I think the diff context figures this out
in a complicated way, but intuitively I'd just look at set differences to figure this out. This function is really useful because
it directly states what we might consider rules. Even if I don't understand how libabigail internally figures this out, these make sense to me:

```cpp
  return (soname_changed() || architecture_changed()
	  || stats.net_num_func_removed() != 0
	  || (stats.num_func_with_virtual_offset_changes() != 0
	      // If all reports about functions with sub-type changes
	      // have been suppressed, then even those about functions
	      // that are virtual don't matter anymore because the
	      // user willingly requested to shut them down
	      && stats.net_num_func_changed() != 0)
	  || stats.net_num_vars_removed() != 0
	  || stats.net_num_removed_func_syms() != 0
	  || stats.net_num_removed_var_syms() != 0
	  || stats.net_num_removed_unreachable_types() != 0
	  || stats.net_num_changed_unreachable_types() != 0);
}
```

And these same kind of checks are defined in [the reporter file](https://github.com/woodard/libabigail/blob/1d29610d51280011a5830166026151b1a9a95bba/src/abg-leaf-reporter.cc#L42).
We already discussed soname or architecture changing. We can derive rules for the rest!

### Rule 5. Net number of functions removed

If this number is not zero, the ABI is not compatible. If we remove a function,
I suspect it needs to be filtered out. If it's not filtered out, then it's still needed.

```cpp
/// Getter for the net number of function removed.
///
/// This is the difference between the number of functions removed and
/// the number of functons removed that have been filtered out.
///
/// @return the net number of function removed.
size_t
corpus_diff::diff_stats::net_num_func_removed() const
{
  ABG_ASSERT(num_func_removed() >= num_removed_func_filtered_out());
  return num_func_removed() - num_removed_func_filtered_out();
}
```

### Rule 6. Functions with virtual offset changes

If the number of functions with virtual offset changes is != 0, it's not ABI compatible.


### Rule 7. Functions with sub-type changes

Note the comment from above:

```cpp
// If all reports about functions with sub-type changes
// have been suppressed, then even those about functions
// that are virtual don't matter anymore because the
// user willingly requested to shut them down
&& stats.net_num_func_changed() != 0)
```

And this is another comparison between a set of changed, and those filtered out.

```cpp
/// Getter for the number of functions that have a change in their
/// sub-types, minus the number of these functions that got filtered
/// out from the diff.
///
/// @return for the the number of functions that have a change in
/// their sub-types, minus the number of these functions that got
/// filtered out from the diff.
size_t
corpus_diff::diff_stats::net_num_func_changed() const
{return num_func_changed() - num_changed_func_filtered_out();}
```

We probably need to trace each of these types in the diff context to see where they
are populated. My goal now is just to write out the checks and maybe we can fill in
the details after if it's not intuitive.

### Rule 8. Variables and functions that are removed

The net number of variables and functions removed must be 0 for abi compatibility.

```cpp
/// Getter for the net number of removed variables.
///
/// The net number of removed variables is the difference between the
/// number of removed variables and the number of removed variables
/// that have been filtered out.
///
/// @return the net number of removed variables.
size_t
corpus_diff::diff_stats::net_num_vars_removed() const
{
  ABG_ASSERT(num_vars_removed() >= num_removed_vars_filtered_out());
  return num_vars_removed() - num_removed_vars_filtered_out();
}
```
I'm grouping these together because they are both symbols. Arguably they could be separate
rules.

```cpp
|| stats.net_num_removed_func_syms() != 0
|| stats.net_num_removed_var_syms() != 0
```

### Rule 9. Removed and changed unreachable types

I'm curious why unreachable types would matter? If we can't reach them, why would
an external library care?

```cpp
|| stats.net_num_removed_unreachable_types() != 0
|| stats.net_num_changed_unreachable_types() != 0);
```

It looks like [has_net_changes](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L358)
does not necessarily indicate incompatability, but [has_incompatible_changes](https://github.com/woodard/libabigail/blob/master/tools/abicompat.cc#L373) does.

So - I think the crux of understanding libabigail comes down to understanding each of these
`calculate_diff` functions, and how the results are populated into the diff context that
is then used to run these higher level functions that count different kinds of changes.
I think we should review the different ones together at whatever level of detail is important
for understanding.

## Issues

**Metabugs** are kept [here](https://sourceware.org/bugzilla/show_bug.cgi?id=27019). We should go through
these and decide which are relevant for discussion here (vs. being a libabigail bug).

1. **Abicompat does not check calls from a library into functions provided by an application** ([ref](https://sourceware.org/bugzilla/show_bug.cgi?id=27208))
2. **Pruning ABI corpora** seems like a good idea but could be problematic. See [1](https://sourceware.org/pipermail/libabigail/2021q1/003237.html), concerned response [2](https://sourceware.org/pipermail/libabigail/2021q1/003247.html) and [3](https://sourceware.org/pipermail/libabigail/2021q1/003249.html).
