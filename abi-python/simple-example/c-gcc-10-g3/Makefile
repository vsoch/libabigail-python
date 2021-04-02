all:
	gcc-10 -g3 -fPIC -Wall -shared -o libmath-v1.so MathLibrary.c
	gcc-10 -g3 -fPIC -Wall -shared -o libmath-v2.so MathLibraryChanged.c
	gcc-10 -g3 -fPIC -Wall -o math-client MathClient.c -I . -L. libmath-v1.so

