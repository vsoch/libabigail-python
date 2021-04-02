all:
	icc -g -fPIC -Wall -shared -o libmath-v1.so MathLibrary.c
	icc -g -fPIC -Wall -shared -o libmath-v2.so MathLibraryChanged.c
	icc -g -fPIC -Wall -o math-client MathClient.c -I . -L. libmath-v1.so

