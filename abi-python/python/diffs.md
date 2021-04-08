# Compute Diffs

The file [rules.md](rules.md) goes through the high level comparison of libabigail
and glibc, but really most of the logic that we need is in the Compute Diffs functions,
which I can inspect for each type. This will be the goal of this file. After going
through this exercise, it feels like most of the logic in this file is to unwrap
items that are nested and hand them off to some core / base functions that compare
types.

Other than matching symbols, I'm not sure about the logic at the beginning that decides
that two things should be compared. It kind of feels like we just throw them into
the diff functions, and if the result is null we determine they aren't to be compared,
and otherwise we get a diff back. We probably want to discuss how this works more.

Also after looking through these, I realized there is one level deeper that is probably
more informative, the content of [abg-comp-filter.cc](https://github.com/woodard/libabigail/blob/master/src/abg-comp-filter.cc) that seems to have detailed functions to return true or false when
comparing two specific things. I'll try to review these both separately.

# abi-comparison.cc

## Try to diff

The `try_to_diff` function is a template that serves to direct the two objects
in comparison to the right function. You can see that it hands off the variables
in the function that tries to [compute_diff_by_type](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2797) -
it's a giant OR statement that checks the first and second contenders to diff
against every diff type function, and if any are true we return that diff object.

> Compute the difference between two types.
> The function considers every possible types known to libabigail
> and runs the appropriate diff function on them.
> Whenever a new kind of type decl is supported by abigail, if we
> want to be able to diff two instances of it, we need to update
> this function to support it.

In the case of calling it without a typename,
we check if the objects are pointers to the same thing, and if:

 - the first is but the second not, we return a null pointer value (I think this is `diff_sptr`)?
 - the first is and the second is, we run `compute_diff` on the two for the type
 - otherwise we return a null pointer value
 
The second version of the function expects a a class declaration (`class_decl`).

> This is a specialization of @ref try_to_diff() template to diff  instances of @ref class_decl.

We again:

 - check if they are both pointers, return null value if one is but not the other.
 - For each, we then compare the attributes `get_is_declaration_only` and `get_definition_of_declaration` and set our object to compare to be the first (unless the second is defined)
 - And finally we calculate `compute_diff` again. 


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
 
It's a general function that seems like a router to get the objects to compare to the right function:

> Compute the difference between two decls.
> The function consider every possible decls known to libabigail and
> runs the appropriate diff function on them.
> Whenever a new kind of non-type decl is supported by abigail, if
> we want to be able to diff two instances of it, we need to update
> this function to support it.

Note the last part of the comment - that we have to update the function if a new
non-type declaration is supported. This also tells us what libabigail thinks
are important to compare. The three types (variables, functions, distinct kinds)
are all discussed separately in this document.

## Compute Diff for Declaration Bases

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3108)

This is to compare type `decl_base_sptr`.


> Compute the difference between two decls.  The decls can represent
> either type declarations, or non-type declaration.
> Note that the two decls must have been created in the same @ref
> environment, otherwise, this function aborts.

It looks like if either is null, we return a null diff object. Does a null
diff object assume that we just can't make an evaluation (because it's not a diff?)
Otherwise, if they are both types, we call `compute_diff_for_types`. If not,
we call `compute_diff_for_decls`.

@woodard tried to explain to me once what an environment is, but I didn't
really follow. It's not really describing what I would expect it to.

## Compute Diff for Type Bases

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3141)

This function is another router - we first get the type declarations
of each, and if they are defined, we compare them with `compute_diff_for_types`
which then is going to call `try_to_diff` in many ways.


## Compute Diff for Distinct Kinds

- [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2750)

> Try to diff entities that are of distinct kinds.
> @param first the first entity to consider for the diff.
> @param second the second entity to consider for the diff.
> @param ctxt the context of the diff.
> @return a non-null diff if a diff object could be built, null otherwise.

It looks like (following a few function calls) the logic here falls back to [this function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L2599),
"entities_are_of_distinct_kinds" where we call them different if they are distinct kinds:

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

It seems like libabigail runs this across all pairs as some kind of sanity check?
For the facts we are generating, if we start with parsed DIE entries
of variable / function types, how would we ever have this case of two "distinct kinds"
of possibly different types being compared? We probably want to better understand
the context of this function to answer that.

## Compute Diff for Pointer Types

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3451)

The pointers also need to be created in the same environment. For this function,
it looks like we compare the types:

```cpp
diff_sptr d = compute_diff_for_types(first->get_pointed_to_type(),
				       second->get_pointed_to_type(),
				       ctxt);
```

And then return a result of type `pointer_diff` with that outcome. So it's
basically unwrapping the pointers and computing a diff for whatever it finds.

## Compute Diff for Arrays

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3619)

We again compare environments first. Then it looks like we compare the element
types:

```cpp
  diff_sptr d = compute_diff_for_types(first->get_element_type(),
				       second->get_element_type(),
				       ctxt);
```
@mplegendre and I had looked at this together and we noticed that we aren't actually
comparing the lengths of the array. We again return a result of an `array_diff` type
with whatever the outcome of the call above is.

## Compute Diff for References

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3764)

For references, we again first compare the environments, and (akin to pointers),
just get the type that the reference is referencing.

```cpp

  diff_sptr d = compute_diff_for_types(first->get_pointed_to_type(),
				       second->get_pointed_to_type(),
				       ctxt);
```

We take the result of that and wrap it in a `result` with a `reference_diff`.


## Compute Diff for Qualified Types

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3924)

We again compare environments first. I'm not actually sure what a qualified type is, but
it looks like we have an underlying type, and that's what is actually compared.

```cpp
diff_sptr d = compute_diff_for_types(first->get_underlying_type(),
				       second->get_underlying_type(),
				       ctxt);
```

And we return that in a result wrapping `qualified_type_diff`.

## Compute Diff for Enum Type Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L4148)

We first compare environments. Then we again get the underlying type:

```cpp

  diff_sptr ud = compute_diff_for_types(first->get_underlying_type(),
					second->get_underlying_type(),
					ctxt);
```
Unlike others that take this approach, it looks like we then iterate through
each in the set (in the enum?) and compare them all:

```cpp
  compute_diff(first->get_enumerators().begin(),
	       first->get_enumerators().end(),
	       second->get_enumerators().begin(),
	       second->get_enumerators().end(),
	       d->priv_->enumerators_changes_);
```

I was expecting this to jump to a function with at least 5 arguments, but when
I used ctags it took me to the compute_diff for an array type [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3630). That must be syntax
to iterate through both sets and compare them. But if the sets are different
lengths, then I suspect we would get a null diff object back and just not be able
to compare them.

## Compute Diff for Class Type Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L5641)

We again start by comparing environments. We then want to know if it's really a class type,
calling this function:

```cpp
/// If a class (or union) is a decl-only class, get its definition.
/// Otherwise, just return the initial class.
///
/// @param the_class the class (or union) to consider.
///
/// @return either the definition of the class, or the class itself.
class_or_union*
look_through_decl_only_class(class_or_union* the_class)
{return is_class_or_union_type(look_through_decl_only(the_class));}
```
And giving the result to `is_class_type`, and that's the content of the `class_diff`

```cpp
class_decl_sptr f = is_class_type(look_through_decl_only_class(first)),
    s = is_class_type(look_through_decl_only_class(second));

  class_diff_sptr changes(new class_diff(f, s, ctxt));
```
Most of the above seems like another way to "unwrap" a class. I'm not
sure how this is represented in DIEs, where we either find structure or
class tags. I suspect the class tag can possibly have different formats (
hence the logic above). It looks like we create a `class_diff_sptr`
called "changes" and then in the case that there isn't a canonical diff,
we try to just diff the changes.

```cpp
  if (!ctxt->get_canonical_diff_for(first, second))
    {
      // Either first or second is a decl-only class; let's set the
      // canonical diff here in that case.
      diff_sptr canonical_diff = ctxt->get_canonical_diff_for(changes);
      ABG_ASSERT(canonical_diff);
      ctxt->set_canonical_diff_for(first, second, canonical_diff);
    }
```
There is then a memory optimization for the changes (which I'm skipping over)
and ultimately we are then checking all the base specifiers:

```cpp

  // Compare base specs
  compute_diff(f->get_base_specifiers().begin(),
               f->get_base_specifiers().end(),
               s->get_base_specifiers().begin(),
               s->get_base_specifiers().end(),
               changes->base_changes());
```

Following with ctags, that is again calling the `compute_diff` for an array type
def to unwrap it. It then looks like libabigail made a decision to not compare
member types:

```cpp
  // Do *not* compare member types because it generates lots of noise
  // and I doubt it's really useful.
#if 0
  compute_diff(f->get_member_types().begin(),
               f->get_member_types().end(),
               s->get_member_types().begin(),
               s->get_member_types().end(),
               changes->member_types_changes());
#endif
```
The code above (with the #if 0 wrapper) seems to be commented out by its color.
But we do choose to compare:

 - data members
 - virtual member functions
 - member function templates
 
```cpp
  // Compare data member
  compute_diff(f->get_non_static_data_members().begin(),
               f->get_non_static_data_members().end(),
               s->get_non_static_data_members().begin(),
               s->get_non_static_data_members().end(),
               changes->data_members_changes());

  // Compare virtual member functions
  compute_diff(f->get_virtual_mem_fns().begin(),
               f->get_virtual_mem_fns().end(),
               s->get_virtual_mem_fns().begin(),
               s->get_virtual_mem_fns().end(),
               changes->member_fns_changes());

  // Compare member function templates
  compute_diff(f->get_member_function_templates().begin(),
               f->get_member_function_templates().end(),
               s->get_member_function_templates().begin(),
               s->get_member_function_templates().end(),
               changes->member_fn_tmpls_changes());
```
 
Each of those is again handed to the `compute_diff` for array types.
We don't compare member class templates (this part is again commented out)

```cpp
  // Likewise, do not compare member class templates
#if 0
  compute_diff(f->get_member_class_templates().begin(),
               f->get_member_class_templates().end(),
               s->get_member_class_templates().begin(),
               s->get_member_class_templates().end(),
               changes->member_class_tmpls_changes());
#endif
```

Libabigail then ensure that its lookup tables are populated and returns the changes.
This is probably an implementation detail.

## Compute Diff for Base Classes

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L5876)

This function is for type `class_decl:base_spec_sptr`. We not only check the environment
of the first and second objects directly, but also their actual base classes (that's kind of neat):

```cpp
  if (first && second)
    {
      ABG_ASSERT(first->get_environment() == second->get_environment());
      ABG_ASSERT(first->get_base_class()->get_environment()
	     == second->get_base_class()->get_environment());
      ABG_ASSERT(first->get_environment()
	     == first->get_base_class()->get_environment());
    }
```

We then call `compute_diff` on the base classes directly.

## Compute Diff for Union Type declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L6008)

We first compare environments, and then create a new `union_diff_sptr` called
changes for a `union_diff`.

It looks like the next part is an optimization, and it might be a message copy
pasted from the class type compute diff function because We again see:

> Ok, so this is an optimization.  Do not freak out if it looks weird, because, well, it does look weird. 

I can assure you that I'm not "freaking out," lol. It's the same logic as before, 
something about setting the private data of the new instance to the private data
of its canonical instance. See [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L6031) for the entire comment.
Akin to comparing classes, there is a smaller set of comparisons here, but
two are "commented out" ?

```cpp
  // Compare data member
  compute_diff(first->get_non_static_data_members().begin(),
	       first->get_non_static_data_members().end(),
	       second->get_non_static_data_members().begin(),
	       second->get_non_static_data_members().end(),
	       changes->data_members_changes());

#if 0
  // Compare member functions
  compute_diff(first->get_mem_fns().begin(),
	       first->get_mem_fns().end(),
	       second->get_mem_fns().begin(),
	       second->get_mem_fns().end(),
	       changes->member_fns_changes());

  // Compare member function templates
  compute_diff(first->get_member_function_templates().begin(),
	       first->get_member_function_templates().end(),
	       second->get_member_function_templates().begin(),
	       second->get_member_function_templates().end(),
	       changes->member_fn_tmpls_changes());
#endif
```
I think the "if 0" evaluates to False, so those are skipped. So essentially
we are just comparing data members, but not member function templates or member
functions. I can't say I know why!

## Compute Diff between Scopes

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L6512)

I'm not sure how a scope is represented in DIEs (maybe the is visible attribute, or if
something is private or public?), but we start by comparing environments. And then
we compare all member declarations for the first and second:

```cpp
  compute_diff(first->get_member_decls().begin(),
	       first->get_member_decls().end(),
	       second->get_member_decls().begin(),
	       second->get_member_decls().end(),
	       d->member_changes());
```
This is again calling the `compute_diff` for array types.
I think what we need to figure out / discuss is, given that we are comparing
arrays, what happens if they aren't even the same length?
Note also that there are two functions for comparing scopes, and the second
one [is here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L6552). The first seems to also accept a `scope_diff_sptr`, and it's
called by the second one (without that argument).

## Compute Diff for Function Declaration Parameters

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L6708)

This function is to compare two function parameters, and we first check if either
is null (and return a null diff), and then again compare
the environments. Ultimately we create a new result with a `fn_param_diff`
and return it. This object represents the changes. Digging in:

```cpp
fn_parm_diff::fn_parm_diff(const function_decl::parameter_sptr  first,
                           const function_decl::parameter_sptr  second,
                           diff_context_sptr                    ctxt)
  : decl_diff_base(first, second, ctxt),
    priv_(new priv)
{
  ABG_ASSERT(first->get_index() == second->get_index());
  priv_->type_diff = compute_diff(first->get_type(),
                                  second->get_type(),
                                  ctxt);
  ABG_ASSERT(priv_->type_diff);
}
```

It looks like we are comparing indices (order?) and types.

## Compute Diff for Function Types

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L7001)

If either is null, we return:

```cpp
  if (!first || !second)
    {
      // TODO: implement this for either first or second being NULL.
      return function_type_diff_sptr();
    }
```
And then we check the environment. It then looks like we compare parameters:

```cpp
  diff_utils::compute_diff(first->get_first_parm(),
			   first->get_parameters().end(),
			   second->get_first_parm(),
			   second->get_parameters().end(),
			   result->priv_->parm_changes_);
```
(again using the function to compare arrays).
I also wonder what happens if they have a different number? And we return
a result with `function_type_diff` which doesn't look very interesting:

```cpp
function_type_diff::function_type_diff(const function_type_sptr first,
                                       const function_type_sptr second,
                                       diff_context_sptr        ctxt)
  : type_diff_base(first, second, ctxt),
    priv_(new priv)
{}
```
I think it's just comparing the base types.

## Compute Diff for Function Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L7153)
 
If either is null, it returns this thing:

```cpp  
/// Convenience typedef for a shared pointer to a @ref function_decl type.
typedef shared_ptr<function_decl_diff> function_decl_diff_sptr;
```

Otherwise we again compare environments, and then compare types:

```cpp
  function_type_diff_sptr type_diff = compute_diff(first->get_type(),
                                                   second->get_type(),
                                                   ctxt);
```

and prepare a result with a `func_decl_diff`

```cpp
function_decl_diff::function_decl_diff(const function_decl_sptr first,
                                       const function_decl_sptr second,
                                       diff_context_sptr        ctxt)
  : decl_diff_base(first, second, ctxt),
    priv_(new priv)
{
}
```

Using `decl_diff_base` seems to be common in most of these functions.

```cpp
decl_diff_base::decl_diff_base(decl_base_sptr   first_subject,
                               decl_base_sptr   second_subject,
                               diff_context_sptr        ctxt)
  : diff(first_subject, second_subject, ctxt),
    priv_(new priv)
{}

decl_diff_base::~decl_diff_base()
{}
```

A diff is:

```cpp
///
/// This constructs a diff between two subjects that are actually
/// declarations; the first and the second one.
///
/// @param first_subject the first decl (subject) of the diff.
///
/// @param second_subject the second decl (subject) of the diff.
///
/// @param ctxt the context of the diff.  Note that this context
/// object must stay alive during the entire life time of the current
/// instance of @ref diff.  Otherwise, memory corruption issues occur.
diff::diff(type_or_decl_base_sptr       first_subject,
           type_or_decl_base_sptr       second_subject,
           diff_context_sptr    ctxt)
  : priv_(new priv(first_subject, second_subject,
                   ctxt, NO_CHANGE_CATEGORY,
                   /*reported_once=*/false,
                   /*currently_reporting=*/false))
{}
```

And a "priv" is:

```cpp
/// The private data of the @diff_node_visitor type.
struct diff_node_visitor::priv
{
  diff* topmost_interface_diff;
  visiting_kind kind;

  priv()
    : topmost_interface_diff(),
      kind()
  {}

  priv(visiting_kind k)
    : topmost_interface_diff(),
      kind(k)
  {}
}; // end struct diff_node_visitor
```

I guess it stores data for diffs, a kind and a visitor? Maybe this is the part
that @woodard was saying that walking the structures changes the result? I can't
say I fully understand this. The `NO_CHANGE_CATEGORY` is default:

```cpp
  /// This means the diff node does not carry any (meaningful) change,
  /// or that it carries changes that have not yet been categorized.
  NO_CHANGE_CATEGORY = 0,
```

Which seems to say "I don't know." If we look at this Enum, it looks like
libabigail keeps track of different ways that tree nodes are visited, see [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/include/abg-comparison.h#L278).

## Compute Diff for Type Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L7283)

We again first compare environments, then we create a diff of type `type_decl_diff`
which doesn't seem super interesting:

```cpp
type_decl_diff::type_decl_diff(const type_decl_sptr first,
                               const type_decl_sptr second,
                               diff_context_sptr ctxt)
  : type_diff_base(first, second, ctxt)
{}
```

Note that libabigail doesn't actually compute a diff here:

```cpp
  // We don't need to actually compute a diff here as a type_decl
  // doesn't have complicated sub-components.  type_decl_diff::report
  // just walks the members of the type_decls and display information
  // about the ones that have changed.  On a similar note,
  // type_decl_diff::length returns 0 if the two type_decls are equal,
  // and 1 otherwise.
```

## Compute Diff for TypeDef Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L7455)

This function compares environments, and then underlying types:

```cpp
  diff_sptr d = compute_diff_for_types(first->get_underlying_type(),
				       second->get_underlying_type(),
				       ctxt);
```

And then we return a result with `typedef_diff`

```cpp
typedef_diff::typedef_diff(const typedef_decl_sptr      first,
                           const typedef_decl_sptr      second,
                           const diff_sptr              underlying,
                           diff_context_sptr            ctxt)
  : type_diff_base(first, second, ctxt),
    priv_(new priv(underlying))
{}
```

## Compute Diff for Translation Units

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L7573)

We assert they are both defined, and then check environments. It looks like
the context can be undefined, in which case we reset it and create a new one:

```cpp
  if (!ctxt)
    ctxt.reset(new diff_context);
```

The rest of the function appears to create a `translation_unit_diff`

```cpp
  // TODO: handle first or second having empty contents.
  translation_unit_diff_sptr tu_diff(new translation_unit_diff(first, second,
							       ctxt));
```

which looks like this:

```cpp
translation_unit_diff::translation_unit_diff(translation_unit_sptr first,
                                             translation_unit_sptr second,
                                             diff_context_sptr ctxt)
  : scope_diff(first->get_global_scope(), second->get_global_scope(), ctxt),
    priv_(new priv(first, second))
{
}
```
(possibly comparing scopes?) and then I'm not sure where this goes:

```cpp
  scope_diff_sptr sc_diff = dynamic_pointer_cast<scope_diff>(tu_diff);

  compute_diff(static_pointer_cast<scope_decl>(first->get_global_scope()),
	       static_pointer_cast<scope_decl>(second->get_global_scope()),
	       sc_diff,
	       ctxt);
```

## Compute Diff for Variable Declarations

 - [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3307)

This function also starts by looking at this `environment` thing - we can't
compare two variable declarations that were not created in the same environment.
It looks like we just create a new `var_diff` and return it directly.
I'm not really sure [what is going on here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L3212).

## Compute Diff of Corpora

- [reference](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L11032)

This is the function we already reviewed in [rules.md](rules.md) that starts the
entire comparison process. There is another function below it for corpus groups
that I'm skipping for now.

## has changes

It looks like each type has a function called `has_changes` that typically just asks
if the first is equal to the second, e.g.,

```cpp
/// @return true if the two subjects of the diff are different, false
/// otherwise.
bool
distinct_diff::has_changes() const
{return first() != second();}
```

But some of them (like the array type) do more! For example, here we check
that the names are the same, the size in bits are the same, and alignment in bits 
are the same:

```cpp
/// Return true iff the current diff node carries a change.
///
/// @return true iff the current diff node carries a change.
bool
array_diff::has_changes() const
{
  bool l = false;

  //  the array element types match check for differing dimensions
  //  etc...
  array_type_def_sptr
    f = dynamic_pointer_cast<array_type_def>(first_subject()),
    s = dynamic_pointer_cast<array_type_def>(second_subject());

  if (f->get_name() != s->get_name())
    l |= true;
  if (f->get_size_in_bits() != s->get_size_in_bits())
    l |= true;
  if (f->get_alignment_in_bits() != s->get_alignment_in_bits())
    l |= true;

  l |=  element_type_diff()
    ? element_type_diff()->has_changes()
    : false;

  return l;
}
```

The only other different ones are scope diffs, which looks  at if size changed:

```cpp
/// Return true iff the current diff node carries a change.
///
/// Return true iff the current diff node carries a change.
bool
scope_diff::has_changes() const
{
  // TODO: add the number of really removed/added stuff.
  return changed_types().size() + changed_decls().size();
}
```

and then the parent function of all of those:

```cpp
/// Return true iff the current @ref corpus_diff node carries a
/// change.
///
/// @return true iff the current diff node carries a change.
bool
corpus_diff::has_changes() const
{
  return (soname_changed()
	  || architecture_changed()
	  || !(priv_->deleted_fns_.empty()
	       && priv_->added_fns_.empty()
	       && priv_->changed_fns_map_.empty()
	       && priv_->deleted_vars_.empty()
	       && priv_->added_vars_.empty()
	       && priv_->changed_vars_map_.empty()
	       && priv_->added_unrefed_fn_syms_.empty()
	       && priv_->deleted_unrefed_fn_syms_.empty()
	       && priv_->added_unrefed_var_syms_.empty()
	       && priv_->deleted_unrefed_var_syms_.empty()
	       && priv_->deleted_unreachable_types_.empty()
	       && priv_->added_unreachable_types_.empty()
	       && priv_->changed_unreachable_types_.empty()));
}
```
So I think the above is called after the entire tree has been traversed,
and any of those particular attributes not being empty indicates there is a change.
This also hints that it's being stored in whatever this "priv" attribute is.

# abg-comp-filter.cc

I kind of think that libabigail goes back retroactively and, for a diff that
is identified, then runs it through [a filter](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L9816) to determine
why it's different (maybe for a human readable thing). Or it could be that we do these checks when a node is visited. The
more I read this code base the less I'm sure about any of this. It's not totally clear to me
when the functions in this file get called (outside of apply_filter) but I suspect they
help to categorize the kind of differences. So I think just reading them verbatim can help us understand what
is going on. 

Notably, if we look at when we create a diff context, it sets up this filter [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comparison.cc#L894)
as the "default" traverse function:

```cpp
diff_context::diff_context()
  : priv_(new diff_context::priv)
{
  // Setup all the diff output filters we have.
  filtering::filter_base_sptr f;

  f.reset(new filtering::harmless_harmful_filter);
  add_diff_filter(f);

  // f.reset(new filtering::harmless_filter);
  // add_diff_filter(f);

  // f.reset(new filtering::harmful_filter);
  // add_diff_filter(f);
}
```
So maybe this `harmless_harmful_filter` is the default (and the others are skipped as
they are commented out?). This filter is defined [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L1738) and it calls
functions to categorize each of harmless and harmful diff nodes for a visit start:

```cpp
bool
harmless_harmful_filter::visit(diff* d, bool pre)
{
  return (categorize_harmless_diff_node(d, pre)
	  && categorize_harmful_diff_node(d, pre));
}
```

and end (probably not useful for us to understand since it's just closing things up
for whatever the libabigial implementation is). I think there is a lot of information in
the functions for [categorize_harmless_diff_node](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L1599) and 
[categorize_harmful_diff_node](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L1687). Specifically:

## categorize_harmless_diff_node

The default value for the kind of change is 
`NO_CHANGE_CATEGORY`. This might mean "it's not harmful" or just "I don't know."

A diff node is harmless if:

**it doesn't have any changes**

```cpp
if (!d->has_changes())
    return true;
```

**if it's a class or enum declaration only change**

```cpp
      if (has_class_decl_only_def_change(d)
	  || has_enum_decl_only_def_change(d))
	category |= TYPE_DECL_ONLY_DEF_CHANGE_CATEGORY;
```

For the class declaration only change, they both need to be defined,
have the same qualified names, and both be declarations only to be true.

```cpp
bool
has_class_decl_only_def_change(const class_or_union_sptr& first,
                               const class_or_union_sptr& second)
{
  if (!first || !second)
    return false;

  class_or_union_sptr f =
    look_through_decl_only_class(first);
  class_or_union_sptr s =
    look_through_decl_only_class(second);

  if (f->get_qualified_name() != s->get_qualified_name())
    return false;

  return f->get_is_declaration_only() != s->get_is_declaration_only();
}
```

For the second we possibly walk through the enum and call the function on itself

```cpp
/// Test if a enum_diff carries a change in which the two enums are
/// different by the fact that one is a decl-only and the other one is
/// defined.
///
/// @param diff the diff node to consider.
///
/// @return true if the enum_diff carries a change in which the two
/// enums are different by the fact that one is a decl-only and the
/// other one is defined.
bool
has_enum_decl_only_def_change(const diff *diff)
{
  const enum_diff *d = dynamic_cast<const enum_diff*>(diff);
  if (!d)
    return false;

  enum_type_decl_sptr f = look_through_decl_only_enum(d->first_enum());
  enum_type_decl_sptr s = look_through_decl_only_enum(d->second_enum());

  return has_enum_decl_only_def_change(f, s);
}
```

**if it's an access changes**

```cpp
 if (access_changed(f, s))
	category |= ACCESS_CHANGE_CATEGORY;
```
which basically says that they both need to be member declarations, and
they "member access specifiers" need to be the same:

```cpp
static bool
access_changed(const decl_base_sptr& f, const decl_base_sptr& s)
{
  if (!is_member_decl(f)
      || !is_member_decl(s))
    return false;

  access_specifier fa = get_member_access_specifier(f),
    sa = get_member_access_specifier(s);

  if (sa != fa)
    return true;

  return false;
}
```
in order for the change to be harmless.

**if it's a compatible change**

```cpp
f (is_compatible_change(f, s))
	category |= COMPATIBLE_TYPE_CHANGE_CATEGORY;
```

which seems to require that they both are defined, not equal, but the types
are compatible.

```cpp
static bool
is_compatible_change(const decl_base_sptr& d1, const decl_base_sptr& d2)
{
  if ((d1 && d2)
      && (d1 != d2)
      && types_are_compatible(d1, d2))
    return true;
  return false;
}
```

**if there is a harmless name change OR a class diff has a harmless odr violation**

```cpp
if (has_harmless_name_change(f, s)
          || class_diff_has_harmless_odr_violation_change(d))
        category |= HARMLESS_DECL_NAME_CHANGE_CATEGORY;
```

[has_harmless_name_change](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L432) is only considered for a typedef or data
member. It is fairly well documented.

A harmless name change happens if:

1. an anonymous declaration name changed into another anonymous declaration change OR
2. a typedef name change without having the underlying type changed OR
3. a data member name change without having its type changed OR
4. an enum name change without having any other part of the enum to change.

[class_diff_has_harmless_odr_violation_change](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L592) is also well documented! 

```cpp
/// Test if a class_diff node has a harmless "One Definition Rule"
/// violation that will cause a diagnostic rule.
///
/// The conditions this function looks for are:
///
///  1/ The two subject of the diff must be canonically different
///
///  2/ The two subjects of the diff must be structurally equal
///
///  3/ The canonical types of the subjects of the diff must be
///  structurally different.
///
/// These conditions makes the diff node appears as it carries changes
/// (because of a ODR glitch present in the binary), but the glitch
/// has no effect on the structural equality of the subjects of the
/// diff.  If we do not detect these conditions, we'd end up with a
/// diagnostic glitch where the reporter thinks there is an ABI change
/// (because of the canonical difference), but then it fails to give
/// any detail about it, because there is no structural change.
```

**if a union diff has harmless changes**

```cpp
 if (union_diff_has_harmless_changes(d))
        category |= HARMLESS_UNION_CHANGE_CATEGORY;
```

This seems to be looking at changes that don't impact the size. The change
is harmless if it's a union diff, the diff has changes, but does not have type
size changes.

**if there are non virtual memory fuction changes**

```cpp
      if (has_non_virtual_mem_fn_change(d))
        category |= NON_VIRT_MEM_FUN_CHANGE_CATEGORY;
```

For these changes to be harmless under this category, we require having a diff
the diff cannot involve a declaration only class, and it looks like we look through
each of deleted, inserted, and changed member functions, and exit early with "yes this
is of this category, a harmless change" if any of them are not virtual:

```cpp
static bool
has_non_virtual_mem_fn_change(const class_diff* diff)
{
  if (!diff || diff_involves_decl_only_class(diff))
    return false;

  for (string_member_function_sptr_map::const_iterator i =
         diff->deleted_member_fns().begin();
       i != diff->deleted_member_fns().end();
       ++i)
    if (!get_member_function_is_virtual(i->second))
      return true;

  for (string_member_function_sptr_map::const_iterator i =
         diff->inserted_member_fns().begin();
       i != diff->inserted_member_fns().end();
       ++i)
    if (!get_member_function_is_virtual(i->second))
      return true;

  for (function_decl_diff_sptrs_type::const_iterator i =
         diff->changed_member_fns().begin();
       i != diff->changed_member_fns().end();
       ++i)
    if(!get_member_function_is_virtual((*i)->first_function_decl())
       && !get_member_function_is_virtual((*i)->second_function_decl()))
      return true;

  return false;
}
```

I don't know why we wouldn't want to check them all, or why finding one non virtual
function is grounds to call it harmless?

**if a static data member is added or removed OR a static data member type size changed**

```cpp
 if (static_data_member_added_or_removed(d)
          || static_data_member_type_size_changed(f, s))
        category |= STATIC_DATA_MEMBER_CHANGE_CATEGORY;
```
For the first, we cut out early and return true if any inserted or
deleted data members are static (I again don't follow this logic):

```cpp
tatic bool
static_data_member_added_or_removed(const class_diff* diff)
{
  if (diff && !diff_involves_decl_only_class(diff))
    {
      for (string_decl_base_sptr_map::const_iterator i =
             diff->inserted_data_members().begin();
           i != diff->inserted_data_members().end();
           ++i)
        if (get_member_is_static(i->second))
          return true;

      for (string_decl_base_sptr_map::const_iterator i =
             diff->deleted_data_members().begin();
           i != diff->deleted_data_members().end();
           ++i)
        if (get_member_is_static(i->second))
          return true;
    }

  return false;
}
```

For the second, we require both to be member declarations, both to have
some kind of dynamic pointer cast, and both of those to not be static. Then
we call `type_size_changed` on the types of the pointers, 

**if a data member is replaced by an anonymous data member**

```cpp
if (has_data_member_replaced_by_anon_dm(d))
        category |= HARMLESS_DATA_MEMBER_CHANGE_CATEGORY;
```

And this is described well in the docstring:

```cpp
/// Test if a @ref class_or_union_diff has a data member replaced by
/// an anonymous data member in a harmless way.  That means, the new
/// anonymous data member somehow contains the replaced data member
/// and it doesn't break the layout of the containing class.
```

**if the diff has an enumerator insertion, and it's not a harmful enum change OR has a harmless enum to int change**

```cpp
if ((has_enumerator_insertion(d)
           && !has_harmful_enum_change(d))
          || has_harmless_enum_to_int_change(d))
        category |= HARMLESS_ENUM_CHANGE_CATEGORY;
```

For the first, a harmful enum change seems to be if it's removed or changed OR has a type size
change:

```cpp
has_harmful_enum_change(const diff* diff)
{
  if (const enum_diff* d = dynamic_cast<const enum_diff*>(diff))
    return (has_enumerator_removal_or_change(d)
            || has_type_size_change(d));
  return false;
}
```

**if a function name changed but not the symbol**

```cpp
if (function_name_changed_but_not_symbol(d))
        category |= HARMLESS_SYMBOL_ALIAS_CHANGE_CATEGORY;
```

Does that happen?

```cpp
/// Test if the current diff tree node carries a function name change,
/// in which there there was no change in the name of the underlying
/// symbol.  IOW, if the name of a function changed, but the symbol of
/// the new function is equal to the symbol of the old one, or is
/// equal to an alians of the symbol of the old function.

```

**if the function parameter diff has a top cv qualifier change on the type, return type, or variable type of the function parameter**

```cpp
      if (has_fn_parm_type_top_cv_qual_change(d))
        category |= FN_PARM_TYPE_TOP_CV_CHANGE_CATEGORY;
```

This one has a lot of conditions for "bailing out" - e.g., if there isn't a diff or no changes.
We then get the first and second parameter from the diff, get their types, and
ensure they are both qualified (otherwise return false). I'm not sure I follow the rest - I don't
know what a CV is or a peeled type.

The rest of the checks are similar but for different attributes (e.g., return or variable)

```cpp
      if (has_fn_return_type_cv_qual_change(d))
        category |= FN_RETURN_TYPE_CV_CHANGE_CATEGORY;

      if (has_var_type_cv_qual_change(d))
        category |= VAR_TYPE_CV_CHANGE_CATEGORY;
```


The second seems to consider that an enum changing to an integer is also okay, the
function is [here](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L1249).

**if it has a void pointer to pointer change**

```cpp
if (has_void_ptr_to_ptr_change(d))
        category |= VOID_PTR_TO_PTR_CHANGE_CATEGORY;
```
or 

**if it has a benign infinite array change**

```cpp
if (has_benign_infinite_array_change(d))
        category |= BENIGN_INFINITE_ARRAY_CHANGE_CATEGORY;
```


And we can only make most of these assertions if it's being visited before it's children
(the variable pre).

## categorize_harmful_diff_node

[This function](https://github.com/woodard/libabigail/blob/40aab37cf04214504804ae9fe7b6c7ff4fd1500f/src/abg-comp-filter.cc#L1687) returns true if the diff doesn't have changes, which means that
the harmless function was non-conclusive but there aren't any changes. I guess both
fuctions return true but don't do anything? Why don't they return false?

This function also defaults to `NO_CHANGE_CATEGORY` but only if pre (if the children
have not been visited) is true. A diff change is considered harmful if:

**if there is a class or enum declaration change and a type size change**

```cpp
if (!has_class_decl_only_def_change(d)
	  && !has_enum_decl_only_def_change(d)
	  && (type_size_changed(f, s)
	      || data_member_offset_changed(f, s)
	      || non_static_data_member_type_size_changed(f, s)
	      || non_static_data_member_added_or_removed(d)
	      || base_classes_added_or_removed(d)
	      || has_harmful_enum_change(d)))
	category |= SIZE_OR_OFFSET_CHANGE_CATEGORY;
```
either meaning:

- a data member offset change
- a non static data member type size change
- a non static data member added or removed
- a base class added or removed
- or a harmful enum change.


or

**if there is a virtual memory function changed**

```cpp
if (has_virtual_mem_fn_change(d))
        category |= VIRTUAL_MEMBER_CHANGE_CATEGORY;

```

This seems like quite a smaller set.


# Next Steps

I still think we need to go over this together and decide what specific checks
we think are important, and then make a list. Once we have that, I want to create
dummy tests (something in cpp to check with libabigial, and our facts checker) to
see if we get the same answer.
