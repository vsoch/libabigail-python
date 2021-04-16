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

% A symbol is undefined if:
symbol_is_undefined(Corpus, Symbol)
    :- symbol(Symbol),
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

% A symbol is missing if
symbol_is_missing(Corpus, Symbol)

  % it's the corpus we are interested in
  :- is_main_corpus(Corpus),

  % it's undefined for that corpus
  symbol_is_undefined(Corpus, Symbol),
  
  % and it's not defined anywhere else
  not symbol_is_defined(Symbol).


% A symbol is missing across needed corpora if
symbol_is_missing(Symbol)

  % if it's missing for any corpus we are interested in
  :- symbol_is_missing(_, Symbol).
  
% STOPPED HERE - we are still missing system includes, there is no way
% to tell what symbol is missing because it's in a system include vs. it should
% be in a dependency (but is not)

#show symbol_is_missing/1. 
