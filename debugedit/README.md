# Debugedit

We can easily edit header information (specifically, directory paths where we compile)
with debugedit. This container will install debugedit, and then demonstrate usage.

```bash
$ docker build -t debugedit .
```

Run an interactive container, binding the present working directory.

```bash
$ docker run -it --rm -v $PWD/:/code debugedit
```

Compile the files - they will have paths to `/code`. We can see that by looking
at them as follows:

```bash
# readelf --string-dump=.debug_str libmath-v1.so

String dump of section '.debug_str':
  [     0]  Divide
  [     7]  MathLibrary.cpp
  [    17]  GNU C++14 9.3.0 -mtune=generic -march=x86-64 -g -fasynchronous-unwind-tables -fstack-protector-strong -fstack-clash-protection -fcf-protection
  [    a6]  double
  [    ad]  Multiply
  [    b6]  /code/simple-example
  [    cb]  Subtract
  [    d4]  Arithmetic
  [    df]  _ZN11MathLibrary10Arithmetic8MultiplyEdd
  [   108]  _ZN11MathLibrary10Arithmetic6DivideEdd
  [   12f]  MathLibrary
  [   13b]  _ZN11MathLibrary10Arithmetic3AddEdd
  [   15f]  _ZN11MathLibrary10Arithmetic8SubtractEdd

```
```bash
root@ab28be05dcbd:/code/simple-example# readelf --string-dump=.debug_str libmath-v1.so | sed -n '/\/\|\.c/{s/.*\]  //p}'
MathLibrary.cpp
/code/simple-example
```

Let's try using debugedit now:

```bash
# debugedit -b /code -d /newdir libmath-v1.so 
root@ab28be05dcbd:/code/simple-example# readelf --string-dump=.debug_str libmath-v1.so

String dump of section '.debug_str':
  [     0]  Arithmetic
  [     b]  _ZN11MathLibrary10Arithmetic3AddEdd
  [    2f]  _ZN11MathLibrary10Arithmetic6DivideEdd
  [    56]  _ZN11MathLibrary10Arithmetic8SubtractEdd
  [    7f]  _ZN11MathLibrary10Arithmetic8MultiplyEdd
  [    a8]  Divide
  [    af]  double
  [    b6]  /newdir/simple-example
  [    cd]  GNU C++14 9.3.0 -mtune=generic -march=x86-64 -g -fasynchronous-unwind-tables -fstack-protector-strong -fstack-clash-protection -fcf-protection
  [   15c]  MathLibrary.cpp
  [   16c]  Subtract
  [   175]  Multiply
```

Wow, that actually seemed to worK! Is it really that easy?
