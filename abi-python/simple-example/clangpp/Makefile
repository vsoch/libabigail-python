all:
	clang++ -g -Wall -fPIC -shared -o libmath-v1.so MathLibrary.cpp
	clang++ -g -Wall -fPIC -shared -o libmath-v2.so MathLibraryChanged.cpp
	clang++ -g -Wall -o math-client MathClient.cpp -I . -L. libmath-v1.so

