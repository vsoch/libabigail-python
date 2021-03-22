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
both_symbols_undefined(CorpusA, CorpusB, Symbol)
  :- symbol_is_undefined(CorpusA, Symbol),
     symbol_is_undefined(CorpusB, Symbol).

% this is unsafe
% one_symbol_undefined(CorpusA, CorpusB, Symbol)
%  :- symbol_is_undefined(CorpusA, Symbol),
%     not symbol_is_undefined(CorpusB, Symbol).


% Two different corpora share a symbol if they both have it
shared_symbol(CorpusA, CorpusB, Symbol) 
  :- has_symbol(CorpusA, Symbol),
     has_symbol(CorpusB, Symbol),
     CorpusA != CorpusB.

% Two corpora have a compatible symbol if it's shared, and at least one is defined
% This is my attempt to capture an OR
compatible_symbols(CorpusA, CorpusB, Symbol)
   :- shared_symbol(CorpusA, CorpusB, Symbol),
      symbol_is_undefined(CorpusA, Symbol).

compatible_symbols(CorpusA, CorpusB, Symbol)
   :- shared_symbol(CorpusA, CorpusB, Symbol),
      symbol_is_undefined(CorpusB, Symbol).
      
% a missing symbol is not defined in either (indicating we are missing libs)
missing_symbols(CorpusA, CorpusB, Symbol)
   :- shared_symbol(CorpusA, CorpusB, Symbol),
      both_symbols_undefined(CorpusA, CorpusB, Symbol).

% Try to create a count of shared symbols and compatible symbols
get_shared_symbols(S) :- shared_symbol(_, _, S).
get_compatible_symbols(S) :- compatible_symbols(_, _, S).

%type(P) :- addEmployee(_, _, _, P, _, _).

total_shared(N) :- #count{X:get_shared_symbols(X)} = K, K=N.
total_compatible(N) :- #count{X:get_compatible_symbols(X)} = K, K=N.

% count of compatible symbols == count of all shared symbols?
% Answer: 1
% total_compatible(8) total_shared(27)
% TODO: we need to be able to distinguish symbols that are defined with
% elf needed libraries - the set of shared probably includes some of those.

% This is showing the other needed libraries that aren't being parsed - both missing
%#show compatible_symbols/3.
#show total_shared/1.
#show total_compatible/1.
