%=============================================================================
% This logic program expects an entire dump of a spack package and its
% dependencies, including symbols and (a subset) of DIEs for parameters (which
% likely will eventually be provided by dyninst since not all compilers use
% them. We label one or more main binaries as "is_main_corpus," meaning that
% we are assessing functionality of that set in context of the dependencies.
%=============================================================================

%=============================================================================
% Matching function and variable symbols
% symbols are missing if they are needed (present in the working library),
% not undefined in the working library (indicating they come from elsewhere)
% and undefined in both the potential library and binary.
%=============================================================================

% These are symbols to skip checking (profiling and other)
skip_symbol("_ITM_deregisterTMCloneTable").
skip_symbol("__gmon_start__").
skip_symbol("_ITM_registerTMCloneTable").


% A symbol is undefined if:
symbol_is_undefined(Corpus, Symbol)

    % it's a symbol
    :- symbol(Symbol),

    % and it's definition is UND
    symbol_definition(Corpus, Symbol, "UND").

% A symbol is defined anywhere if
symbol_is_defined(Symbol, Definition)

    % it's a symbol
    :- symbol(Symbol),

    % it has a symbol definition
    symbol_definition(_, Symbol, Definition),

    % and definition != UND
    Definition != "UND".

% filter down to just symbol name
symbol_is_defined(Symbol) :- symbol_is_defined(Symbol, _).

% A symbol is needed if:
symbol_is_needed(Corpus, Symbol)

  % it's the corpus we are interested in
  :- is_main_corpus(Corpus),

  % it's not flagged to skip
  not skip_symbol(Symbol),

  % it's undefined for that corpus
  symbol_is_undefined(Corpus, Symbol).

% A symbol is missing if
symbol_is_missing(Corpus, Symbol)

  % it's needed
  :- symbol_is_needed(Corpus, Symbol),
  
  % and it's not defined anywhere else
  not symbol_is_defined(Symbol).


% A symbol is missing uacross needed corpora if
symbol_is_missing(Symbol)

  % if it's missing for any corpus we are interested in
  :- symbol_is_missing(_, Symbol).
  

get_missing_symbols(S) :- symbol_is_missing(S).
count_missing_symbols(N) :- #count{X:get_missing_symbols(X)} = K, K=N.


%=============================================================================
% Single soname and architecture
% libraries must have matching soname and architecture
%=============================================================================

get_architecture(A) :- corpus_machine(_, A).
architecture_count(N) :- #count{X:get_architecture(X)} = K, K=N.

get_soname(A) :- corpus_soname(_, A).
soname_count(N) :- #count{X:get_soname(X)} = K, K=N.


%=============================================================================
% Parameter matching, C++ and C
% To do parameter matching, we have to compare the working library against
% the library in question to compare parameter types. If we are dealing with
% C, the symbols can still match even if function args do not.

% parameter types
% parameter sizes
% parameter counts
% structures part of a parameter, look at layout of structures?
%=============================================================================

% C++ will subset that set to those with a mangled name
library_has_function(Corpus, Id, Symbol)

      % it has a mangled string with a symbol
      :- dw_tag_function_mangled_name(Corpus, Id, Symbol).

% OR
      
% C: doesn't have mangled name, uses name instead
library_has_function(Corpus, Id, Symbol)

      % it has a mangled string with a symbol
      :- dw_tag_function_name(Corpus, Id, Symbol).


% Find needed functions for a main corpus
function_is_needed(Corpus, Symbol, Id)

    % corpusA is the library that works
    :- is_main_corpus(Corpus),

       % Both have a symbol with the same name
       library_has_function(Corpus, Id, Symbol).

% subset to needed function names
is_needed_function(S) :- function_is_needed(_, S, _).

% A function that is needed is matched to another library
matching_functions(CorpusA, CorpusB, Symbol, IdA, IdB)

   % if it's known to be needed by a main corpus
   :- function_is_needed(CorpusA, Symbol, IdA),
      library_has_function(CorpusB, IdB, Symbol),

      % and the other corpus is not a main corpus
      CorpusA != CorpusB.

   
% Find function matching parameters (based on symbol name, not order)
matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB)

    % included in subset of those that have matching symbols
    :- matching_functions(CorpusA, CorpusB, Symbol, IdA, IdB),
       
       % Each has some child
       has_child(IdA, ChildA),
       has_child(IdB, ChildB),

       % And each child is formal parameters
       dw_tag_formal_parameter(CorpusA, ChildA),
       dw_tag_formal_parameter(CorpusB, ChildB).

% But they are only really matching if the order is the same.
% Paramters are match if:
matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order)

    % they match based on the parent function
    :- matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB),

       % And the order of the child is the same
       dw_tag_formal_parameter_order(CorpusA, ChildA, Order),
       dw_tag_formal_parameter_order(CorpusB, ChildB, Order).


% We also need to know if a parameter is missing - if the order is not there
function_parameters_missing(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order)

    % Subset to those that have matching symbols
    :- matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB),

       % if A is the main corpus
       is_main_corpus(CorpusA),

       % And has a parameter defined
       dw_tag_formal_parameter_order(CorpusA, ChildA, Order),
       
       % But it's not defined elsewhere
       not dw_tag_formal_parameter_order(CorpusB, ChildB, Order).


get_function_parameters_missing(A) :- function_parameters_missing(_,_,A,_,_,_,_,_).
count_function_parameters_missing(N) :- #count{X:get_function_parameters_missing(X)} = K, K=N.


% function params are not equal in size
function_parameters_size_mismatch(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order, SizeA, SizeB)
    % If they are in the same order
    :- matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order),

    % and the sizes are not equal (this returns all pairs of sizes, equal and not)
    dw_tag_formal_parameter_size_in_bits(CorpusA, ChildA, SizeA),
    dw_tag_formal_parameter_size_in_bits(CorpusB, ChildB, SizeB),
    SizeA != SizeB.

get_function_parameters_size_mismatch(A) :- function_parameters_size_mismatch(_,_,_,_,_,_,_,_,_,A).
count_function_parameters_size_mismatch(N) :- #count{X:get_function_parameters_size_mismatch(X)} = K, K=N.

% function params are not equal in type
function_parameters_type_mismatch(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order, TypeA, TypeB)

    % If they are in the same order
    :- matching_parameters(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Order),

    % The type names are not equal
    dw_tag_formal_parameter_type_name(CorpusA, ChildA, TypeA),
    dw_tag_formal_parameter_type_name(CorpusB, ChildB, TypeB),
    TypeA != TypeB.

get_function_parameters_type_mismatch(A) :- function_parameters_type_mismatch(_,_,_,_,_,_,_,_,_,A).
count_function_parameters_type_mismatch(N) :- #count{X:get_function_parameters_type_mismatch(X)} = K, K=N.


%#show symbol_is_missing/1.
%#show get_needed_functions/1.
%#show library_has_function/3.
%#show function_is_needed/3.
%#show function_parameters_missing/8.
%#show matching_functions/5.
%#show matching_parameters/8.
%#show function_parameters_size_mismatch/10.
%#show function_parameters_type_mismatch/10.
#show count_function_parameters_size_mismatch/1.
#show count_function_parameters_type_mismatch/1.
#show count_function_parameters_missing/1.
#show count_missing_symbols/1.
#show architecture_count/1.
#show soname_count/1.
