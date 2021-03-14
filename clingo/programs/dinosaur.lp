% These are blanket facts, statements that each of these is living
% I think these are called atoms
living(vanessa).
living(fernando).
living(maria).

% This tells use size of arms for each living thing
armsize(vanessa, "small").
armsize(fernando, "large").
armsize(fernando, "small").

% A boolean to say we can roar!
canroar(vanessa).

% An entity is a dinosaur if they are living, have tiny arms, and can roar.
dinosaur(Entity) :- living(Entity), armsize(Entity, "small"), canroar(Entity).
