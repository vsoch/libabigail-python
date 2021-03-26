%=============================================================================
% This logic program shows what symbols are compatible. I just started
% writing it and haven't tested anything yet, just trying to figure out
% basic syntx.
%=============================================================================

% Let's try to "set" a corpus A and B (we can eventually do this dynamically)
% main is the binary we are assessing for compatibility against lib
is_main(Corpus) :- corpus_name(Corpus, "math-client").
is_library(Corpus) :- corpus_name(Corpus, "libmath-v2.so").
is_working(Corpus) :- corpus_name(Corpus, "libmath-v1.so").

%=============================================================================
% Matching function and variable symbols
% symbols are missing if they are needed (present in the working library),
% not undefined in the working library (indicating they come from elsewhere)
% and undefined in both the potential library and binary.
%=============================================================================

% A symbol is undefined in this case.
symbol_is_undefined(Corpus, Symbol) :- symbol_definition(Corpus, Symbol, "UND").

% we can ignore a symbol in the library that is known to work (the subset of 
% "needed symbols" if it is undefined. The logic here is that if the main app
% linking with this library works, even if both are undefined, then the symbol
% must be provided by another librarys
not_needed_symbol(Symbol) :- needed_symbol_definition(Symbol, "UND").


% A symbol is considered missing for main if: 
missing_symbols(CorpusA, CorpusB, Symbol)

   % set CorpusA to be main, CorpusB to be linked library
   :- is_main(CorpusA),
      is_library(CorpusB),

      % it's not considered not needed, aka it is defined in the working lib
      not not_needed_symbol(Symbol),

      % it is undefined in the main binary
      symbol_is_undefined(CorpusA, Symbol),

      % it is undefined or missing in the second lib we want to link
      symbol_is_undefined(CorpusB, Symbol).

% OR

% A symbol is considered missing for main if: 
missing_symbols(CorpusA, CorpusB, Symbol)

   % set CorpusA to be main, CorpusB to be linked library
   :- is_main(CorpusA),
      is_library(CorpusB),

      % it's not considered not needed, aka it is defined in the working lib
      not not_needed_symbol(Symbol),

      % it is undefined in the main binary
      symbol_is_undefined(CorpusA, Symbol),

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
% get_soname(A) :- corpus_elf_soname(_, A).
% soname_count(N) :- #count{X:get_soname(X)} = K, K=N.

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
#show architecture_count/1.
#show get_missing_symbols/1.
#show total_missing/1.

%#show is_main/1.
%#show shared_symbol/3.
%#show soname_count/1.
