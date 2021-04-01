%=============================================================================
% This logic program shows what symbols are compatible. Eventually we
% can move different rules into different files (symbols, variables, etc.)
%=============================================================================

% Let's try to "set" a corpus A and B (we can eventually do this dynamically)
% main is the binary we are assessing for compatibility against lib (is_library)
% and is_needed marks the second working library.
is_main(Corpus) :- corpus_name(Corpus, "math-client").
is_library(Corpus) :- corpus_name(Corpus, "libmath-v2.so").
is_needed(Corpus) :- needed_corpus_name(Corpus, "libmath-v1.so").

%=============================================================================
% Matching function and variable symbols
% symbols are missing if they are needed (present in the working library),
% not undefined in the working library (indicating they come from elsewhere)
% and undefined in both the potential library and binary.
%=============================================================================

% A symbol is undefined in this case.
symbol_is_undefined(Corpus, Symbol) :- symbol_definition(Corpus, Symbol, "UND").

% A symbol is hidden in this case (is this useful?)
% This rule is not in use yet
% symbol_is_hidden(Corpus, Symbol) :- symbol_visibility(Corpus, Symbol, "HIDDEN").

% we can ignore a symbol in the library that is known to work (the subset of 
% "needed symbols" if it is undefined). The logic here is that if the main app
% linking with this library works, even if both are undefined, then the symbol
% must be provided by another library

% a symbol is known to be needed if
known_needed_symbol(Symbol)

    % it's present in a linked library that we know towork
    :- needed_symbol(Symbol),

    % and it's not undefined. If a symbol is undefined and still works,
    % we arguably don't care.
    not needed_symbol_definition(_, Symbol, "UND").

% Shared rule for both cases of missing symbol. We have two to express an OR
known_needed_symbol_undefined(CorpusA, CorpusB, Symbol)

   % set CorpusA to be main, CorpusB to be linked library
   :- is_main(CorpusA),
      is_library(CorpusB),

      % it's a known needed symbol
      known_needed_symbol(Symbol),

      % it is undefined in the main binary
      symbol_is_undefined(CorpusA, Symbol).


% A symbol is considered missing for main if: 
missing_symbols(CorpusA, CorpusB, Symbol)

      % a known needed symbol is undefined
      :- known_needed_symbol_undefined(CorpusA, CorpusB, Symbol),

      % it is undefined in the second lib we want to link
      symbol_is_undefined(CorpusB, Symbol).

% OR

% A symbol is considered missing for main if: 
missing_symbols(CorpusA, CorpusB, Symbol)

   % a known needed symbol is undefined
   :- known_needed_symbol_undefined(CorpusA, CorpusB, Symbol),

      % it is not present in the second library
      not has_symbol(CorpusB, Symbol).


% TODO how to enforce unique?
get_missing_symbols(S) :- missing_symbols(_, _, S).
count_missing_symbols(N) :- #count{X:get_missing_symbols(X)} = K, K=N.

%=============================================================================
% Matching soname and architecture
% libraries must have matching soname and architecture
%=============================================================================

% libabigail just compares the libs, but why not compare to the binary too?
%shared_architecture(CorpusA, CorpusB)
%  :- corpus_elf_machine(CorpusA, _, A)
get_architecture(A) :- corpus_elf_machine(_, A).
architecture_count(N) :- #count{X:get_architecture(X)} = K, K=N.

% todo: I don't think my data has sonames, need to add or figure out why not in
% dynamic tags
get_soname(A) :- corpus_elf_soname(_, A).
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

% General function to mark a function based on id and known needed symbol
entity_has_function(Corpus, Id, Symbol)

   % It's marked as a function   
   :- dw_tag_function(Corpus, Id),
      
      % that maches a symbol we know is needed
      known_needed_symbol(Symbol).

% C++ will subset that set to those with a mangled name
library_has_function(Corpus, Id, Symbol)
    :- entity_has_function(Corpus, Id, Symbol),

      % it has a mangled string with a symbol
      dw_tag_function_mangled_name(Corpus, Id, Symbol).

% OR
      
% C: doesn't have mangled name, uses name instead
library_has_function(Corpus, Id, Symbol)
    :- entity_has_function(Corpus, Id, Symbol),

      % it has a mangled string with a symbol
      dw_tag_function_name(Corpus, Id, Symbol).

% Compare function symbols working (needed) and testing library
% For C, they will be the same even if parameters don't match
% Keep track of die ids - we will use them to find parameters
function_symbols_match(CorpusA, CorpusB, Symbol, IdA, IdB)

    % corpusA is the library that works, and B is the one we are testing
    :- is_needed(CorpusA),
       is_library(CorpusB),

       % Both have a symbol with the same name
       needed_dw_tag_function_name(CorpusA, IdA , Symbol),
       dw_tag_function_name(CorpusB, IdB , Symbol).

% First we find matching parameters based on function, formal param, and name
% This assumes we have the same names
function_parameters_match(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Param)

    % Subset to those that have matching symbols
    :- function_symbols_match(CorpusA, CorpusB, Symbol, IdA, IdB),
       
       % Find parameter as a child of the function die
       die_has_child(IdA, ChildA),
       die_has_child(IdB, ChildB),

       % subset to children that are formal parameters
       needed_dw_tag_formal_parameter(CorpusA, ChildA),
       dw_tag_formal_parameter(CorpusB, ChildB),   

       % The formal parameters must have matching name (can we assume with
       % clingo if we use two different variable names, they must be different?
       needed_dw_tag_formal_parameter_name(CorpusA, ChildA, Param),
       dw_tag_formal_parameter_name(CorpusB, ChildB, Param).

% function params are not equal in size
function_parameters_size_mismatch(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Param, SizeA, SizeB)
    :- function_parameters_match(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Param),

    % The sizes are not equal (this returns all pairs of sizes, equal and not)
    needed_dw_tag_formal_parameter_size_in_bits(CorpusA, ChildA, SizeA),
    dw_tag_formal_parameter_size_in_bits(CorpusB, ChildB, SizeB),
    SizeA != SizeB.

get_function_parameters_size_mismatch(A) :- function_parameters_size_mismatch(_,_,_,_,_,_,_,_,_,A).
count_function_parameters_size_mismatch(N) :- #count{X:get_function_parameters_size_mismatch(X)} = K, K=N.

% function params are not equal in type
function_parameters_type_mismatch(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Param, TypeA, TypeB)
    :- function_parameters_match(CorpusA, CorpusB, Symbol, IdA, IdB, ChildA, ChildB, Param),

    % The type names are not equal
    needed_dw_tag_formal_parameter_type_name(CorpusA, ChildA, TypeA),
    dw_tag_formal_parameter_type_name(CorpusB, ChildB, TypeB),
    TypeA != TypeB.

get_function_parameters_type_mismatch(A) :- function_parameters_type_mismatch(_,_,_,_,_,_,_,_,_,A).
count_function_parameters_type_mismatch(N) :- #count{X:get_function_parameters_type_mismatch(X)} = K, K=N.

% Check for the number of parameters the same 
% First write a general rule to find formal parameters
% We want to find shared parameters (via symbols) between main and library
% the library can have extra symbols main doesn't use, and we don't care.
shared_symbols(CorpusA, CorpusB, Symbol)

    % set main and the library
    :- is_main(CorpusA),
       is_library(CorpusB),
       
       % ensure the symbol is present in both
       has_symbol(CorpusA, Symbol),    
       has_symbol(CorpusB, Symbol).

% Now that we have the shared symbols, just reduce to the names
is_shared_symbol(Symbol) :- shared_symbols(_,_,Symbol).


% A general rule to get formal parameters, but only for shared symbols
entity_formal_parameters(Corpus, Id, Symbol, Child)

    % Find all functions for the library or main
    :- library_has_function(Corpus, Id, Symbol),

       % the symbol must be shared
       is_shared_symbol(Symbol), 
                  
       % Find parameter as a child of the function die
       die_has_child(Id, Child),

       % subset to children that are formal parameters (this is for library)
       dw_tag_formal_parameter(Corpus, Child). 


% now we want to check the library vs. main program
library_formal_parameters(Corpus, Id, Symbol, Child)

    % Find all functions for the library or main
    :- entity_formal_parameters(Corpus, Id, Symbol, Child),
     
       % We want to check the library
       is_library(Corpus).

main_formal_parameters(Corpus, Id, Symbol, Child)

    % Find all functions for the library or main
    :- entity_formal_parameters(Corpus, Id, Symbol, Child),
     
       % We want to check the library
       is_main(Corpus).


% Now get counts for each of library and main, and they need to be ==
get_formal_parameter_count_main(Count) :-
    Count = #count { Symbol : main_formal_parameters(_, _, Symbol, _) }.

get_formal_parameter_count_library(Count) :-
    Count = #count { Symbol : library_formal_parameters(_, _, Symbol, _) }.

formal_parameter_counts_equal(CountMain, CountLibrary) :-
    get_formal_parameter_count_library(CountLibrary),
    get_formal_parameter_count_main(CountMain),
    CountLibrary == CountMain.
    

% TODO I will want to print this out more clearly, probably the is_compatible
% can we just add up things that should be zero and determine if it's !=0?
% function could use arguments for Corpora.
% Two corpora are compatible if:
are_compatible()

  % there are no missing symbols
  :- count_missing_symbols(N) == 0.

  % there is only one architecture
  :- architecture_count(N) == 1.
  
%#show both_symbols_undefined/3.
%#show corpus_needs_symbol/2.
%#show corpus_needs_library/2.
#show is_main/1.
#show is_library/1.
#show is_needed/1.

#show get_architecture/1.
#show architecture_count/1.
#show get_soname_count/1.

#show library_formal_parameters/4.
#show main_formal_parameters/4.
#show get_missing_symbols/1.
#show count_missing_symbols/1.
#show get_formal_parameter_count_main/1.
#show get_formal_parameter_count_library/1.
#show formal_parameter_counts_equal/2.
#show count_function_parameters_size_mismatch/1.
#show count_function_parameters_type_mismatch/1.
