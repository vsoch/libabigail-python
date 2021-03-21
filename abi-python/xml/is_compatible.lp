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

% A symbol is undefined/defined if is-defined is no/yes
symbol_is_undefined(Corpus, Symbol) :- symbol_is_defined(Corpus, Symbol, "no").
symbol_is_defined(Corpus, Symbol) :- symbol_is_defined(Corpus, Symbol, "yes").

% Two corpora share a symbol if they both have it
shared_symbol(CorporaA, CorporaB) :- has_symbol(CorporaA, Symbol), has_symbol(CorporaB, Symbol).

% TODO: a symbol needs to be defined in context of a corpus
% Two corpora have a compatible symbol if it's shared, and at least one is defined
compatible_symbols(CorporaA, CorporaB, Symbol)
  -: shared_symbol(CorporaA, CorporaB),
  -: symbol_is_defined(CorpusA, Symbol) | symbol_is_defined(CorpusB, Symbol)

% TODO how do I represent or?
#show compatible_symbols/0.
