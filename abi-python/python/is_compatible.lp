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


% Symbols are needed if they are: and in the needed set
symbol_is_needed(CorpusA, CorpusB, Symbol)

  % shared between the corpora
  :- shared_symbol(CorpusA, CorpusB, Symbol),

    % a needed symbol,
    needed_symbol(Symbol),
    
    % not undefined in the compatible library
    not needed_symbol_is_undefined(Symbol).

% If any needed symbol is undefined for both, they are not compatible
% TODO: this is still missing symbols from other needed libraries, or perhaps
% symbols that are always undefined.
missing_symbols(CorpusA, CorpusB, Symbol)
   :- symbol_is_needed(CorpusA, CorpusB, Symbol),
      both_symbols_undefined(CorpusA, CorpusB, Symbol).

% Two corpora have a compatible symbol if it's shared, and at least one is defined
% This is my attempt to capture an OR
%compatible_symbols(CorpusA, CorpusB, Symbol)
%   :- shared_symbol(CorpusA, CorpusB, Symbol),
%      symbol_is_undefined(CorpusA, Symbol).

%compatible_symbols(CorpusA, CorpusB, Symbol)
%   :- shared_symbol(CorpusA, CorpusB, Symbol),
%      symbol_is_undefined(CorpusB, Symbol).
      
% a missing symbol is not defined in either (indicating we are missing libs)
%missing_symbols(CorpusA, CorpusB, Symbol)
%   :- shared_symbol(CorpusA, CorpusB, Symbol),
%      both_symbols_undefined(CorpusA, CorpusB, Symbol).

% Try to create a count of missing symbols
get_missing_symbols(S) :- missing_symbols(_, _, S).
total_missing(N) :- #count{X:get_missing_symbols(X)} = K, K=N.

%total_compatible(N) :- #count{X:get_compatible_symbols(X)} = K, K=N.


% Two corpora are compatible if:
are_compatible()

  % there are no missing symbols
  :- total_missing(N) = 0.

% TODO I will want to print this out more clearly, probably the is_compatible
% function could use arguments for Corpora.
%#show compatible_symbols/3.
%#show total_shared/1.
%#show total_compatible/1.
#show are_compatible/0.
