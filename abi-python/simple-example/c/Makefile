all:
	gcc -g -Wall -shared -o libmathc-v1.so MathLibrary.c
	gcc -g -Wall -shared -o libmathc-v2.so MathLibraryChanged.c
	gcc -g -Wall -o math-client-c MathClient.c -I . -L. libmathc-v1.so

