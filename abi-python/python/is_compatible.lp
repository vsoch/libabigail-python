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

% Two different corpora share a symbol if they both have it
shared_symbol(CorpusA, CorpusB, Symbol) 
  :- has_symbol(CorpusA, Symbol),
     has_symbol(CorpusB, Symbol),
     CorpusA != CorpusB.

% Two corpora have a compatible symbol if it's shared, and at least one is defined
% This would ideally be an OR instead of two statements.
%compatible_symbols(CorpusA, CorpusB, Symbol)
%   :- shared_symbol(CorpusA, CorpusB, Symbol).
%   not symbol_is_undefined(CorpusA, Symbol).

% compatible_symbols(CorpusA, CorpusB, Symbol)
%  :- shared_symbol(CorpusA, CorpusB, Symbol).
%  not symbol_is_undefined(CorpusA, Symbol).

% TODO how do I represent or?
#show shared_symbol/3.
