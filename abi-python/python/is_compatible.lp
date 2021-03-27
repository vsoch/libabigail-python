%=============================================================================
% This logic program shows what symbols are compatible. Eventually we
% can move different rules into different files (symbols, variables, etc.)
%=============================================================================

% Let's try to "set" a corpus A and B (we can eventually do this dynamically)
% main is the binary we are assessing for compatibility against lib
is_main(Corpus) :- corpus_name(Corpus, "math-client").
is_library(Corpus) :- corpus_name(Corpus, "libmath-v2.so").

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
    not needed_symbol_definition(Symbol, "UND").

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
total_missing(N) :- #count{X:get_missing_symbols(X)} = K, K=N.

% TODOS
% parameter types
% parameter sizes
% parameter counts
% structures part of a parameter, look at layout of structures?

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


% TODO I will want to print this out more clearly, probably the is_compatible
% function could use arguments for Corpora.
% Two corpora are compatible if:
are_compatible()

  % there are no missing symbols
  :- total_missing(N) == 0.

  % there is only one architecture
  :- architecture_count(N) == 1.

%#show shared_symbol/3.
%#show both_symbols_undefined/3.
%#show total_missing/1.
%#show corpus_needs_symbol/2.
%#show corpus_needs_library/2.
#show get_architecture/1.
#show architecture_count/1.
#show get_missing_symbols/1.
#show total_missing/1.
#show soname_count/1.
%#show binary_symbol_has_subprogram/3.
%#show library_symbol_has_subprogram/3.
%#show shared_subprogram_for_needed_symbol/4.
%#show is_main/1.
%#show shared_symbol/3.
%#show soname_count/1.
