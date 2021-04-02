all:
	clang -g -fPIC -Wall -shared -o libmath-v1.so MathLibrary.c
	clang -g -fPIC -Wall -shared -o libmath-v2.so MathLibraryChanged.c
	clang -g -fPIC -Wall -o math-client MathClient.c -I . -L. libmath-v1.so

