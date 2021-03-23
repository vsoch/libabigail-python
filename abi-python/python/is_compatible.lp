%=============================================================================
% This logic program shows what symbols are compatible. I just started
% writing it and haven't tested anything yet, just trying to figure out
% basic syntx.
%=============================================================================


% we probably want a rule about a library needing another one - the issue here
% is that one is a full path, the other is a basename, e.g.
% corpus_needs_library("/code/simple-example/cpp/math-client","libmath-v1.so").
% corpus("/code/simple-example/cpp/libmath-v1.so").
% We can maybe use a basename
% corpus_basename("/code/simple-example/cpp/libmath-v1.so","libmath-v1.so").
% If we are deriving from spack, I also don't see why we can't include 
% other libraries (we are sure about) that are needed to find extra symbols,
% although libabigail doesn't do that.

%=============================================================================
% Matching function and variable symbols
% symbols are missing if they are needed (present in the working library),
% not undefined in the working library (indicating they come from elsewhere)
% and undefined in both the potential library and binary.
%=============================================================================

% A symbol is undefined in this case.
symbol_is_undefined(Corpus, Symbol) :- symbol_definition(Corpus, Symbol, "UND").

% we can ignore a "needed symbol" if it is undefined, because we already know
% the library with needed symbols works. An undefined symbol in this case must
% come from somewhere else.
needed_symbol_is_undefined(Symbol) :- needed_symbol_definition(Symbol, "UND").

both_symbols_undefined(CorpusA, CorpusB, Symbol)
  :- symbol_is_undefined(CorpusA, Symbol),
     symbol_is_undefined(CorpusB, Symbol).


% Two different corpora share a symbol if they both have it
shared_symbol(CorpusA, CorpusB, Symbol) 
  :- has_symbol(CorpusA, Symbol),
     has_symbol(CorpusB, Symbol),
     CorpusA != CorpusB.


% Symbols are needed if they are needed, and defined in the needed set
symbol_is_needed(Symbol)

    % a needed symbol,
    :- needed_symbol(Symbol),
    
      % not undefined in the compatible library
      not needed_symbol_is_undefined(Symbol).

% If any needed symbol is undefined for both, they are not compatible
% TODO: this is still missing symbols from other needed libraries, or perhaps
% symbols that are always undefined.
missing_symbols(CorpusA, CorpusB, Symbol)
   :- symbol_is_needed(Symbol),
      both_symbols_undefined(CorpusA, CorpusB, Symbol).

% Try to create a count of missing symbols
% TODO: this will be double if we count CorpusA, CorpusB and CorpusB, CorpusA (twice)
get_missing_symbols(S) :- missing_symbols(_, _, S).
total_missing(N) :- #count{X:get_missing_symbols(X)} = K, K=N.

%total_compatible(N) :- #count{X:get_compatible_symbols(X)} = K, K=N.


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

#show total_missing/1.
#show architecture_count/1.
%#show soname_count/1.
