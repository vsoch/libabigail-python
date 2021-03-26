all:
	gcc -g -fPIC -Wall -shared -o libmathc-v1.so MathLibrary.c
	gcc -g -fPIC -Wall -shared -o libmathc-v2.so MathLibraryChanged.c
	gcc -g -fPIC -Wall -o math-client-c MathClient.c -I . -L. libmathc-v1.so

