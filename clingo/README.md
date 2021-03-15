# Learning Clingo

This is a small exercise to try writing a few logic programs. Some of them
are provided in this [ASP]() book, and the final ones I'll try writing on my own.
The goal of doing this is to get familiar with logic programming / answer set
programming enough so I could write rules for ABI in this model.

### Development Environment

Since I don't want to install clingo locally, let's make a container! This
is a spack build of clingo from the [autumus registry](https://github.com/orgs/autamus/packages/container/package/clingo)
We will create a local directory of programs and bind to the container for easy
interaction.

```bash
$ mkdir -p programs
$ docker run --rm -v $PWD/programs:/programs -it ghcr.io/autamus/clingo:latest bash
```

Now we can write programs on our host, and run them in the container. Let's cd
to that directory in the container:

```bash
$ cd /programs
```

### Example program: Is a Dinosaur

#### Writing the Logic Program

Let's start with a simple program that makes an assessment if a living thing is
a dinosaur. You can find this in [programs/dinosaur.lp](programs/dinosaur.lp).
Let's start by writing down a bunch of facts about living things.

```lp
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
```

Now that we have our facts, let's write a rule that determines a dinosaur.

```lp
% An entity is a dinosaur if they are living, have tiny arms, and can roar.
dinosaur(Entity) :- living(Entity), armsize(Entity, "small"), canroar(Entity).
```

#### Looking for a solution

And run clingo to see if we have a solution!

```bash
# clingo dinosaur.lp 
clingo version 5.5.0
Reading from dinosaur.lp
Solving...
Answer: 1
canroar(vanessa) armsize(vanessa,"small") armsize(fernando,"large") armsize(fernando,"small") living(vanessa) living(fernando) living(maria) dinosaur(vanessa)
SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.003s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.001s
```

We have concluded that vanessa is a dinosaur! Note that the above shows all atoms. We can
ask clingo to only show the dinosaur atoms by adding this to the file:

```lp
% Show only the dinosaur atoms
#show dinosaur/1.
```
Where "1" is the "arity" - the number of arguments.
