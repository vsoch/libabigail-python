all:
	gcc -g -fPIC -Wall -shared -o libmath-v1.so MathLibrary.c
	gcc -g -fPIC -Wall -shared -o libmath-v2.so MathLibraryChanged.c
	gcc -g -fPIC -Wall -o math-client MathClient.c -I . -L. libmath-v1.so

