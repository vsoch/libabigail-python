# Libabigail Python

This is a small repository to test creating python bindings for [Libabigail](https://sourceware.org/git/?p=libabigail.git;a=tree).
It includes the following sections:

 - [bindings](bindings): early testing of ctypes (and other) to create bindings
 - [wrapper](wrapper): a more "expected" wrapper to just parse the abidw command output into json
 - [abispack-lib](abispack-lib): A C++ library that we would want to use libabigial, and expose some subset of functions to spack (so there would be Python bindings)
 - [libabi-ml](libabi-ml): Starting to think about if it makes sense to restructure the json to provide some subset of features.
