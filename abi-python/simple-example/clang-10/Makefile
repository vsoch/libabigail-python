all:
	clang-10 -g -fPIC -Wall -shared -o libmath-v1.so MathLibrary.c
	clang-10 -g -fPIC -Wall -shared -o libmath-v2.so MathLibraryChanged.c
	clang-10 -g -fPIC -Wall -o math-client MathClient.c -I . -L. libmath-v1.so

