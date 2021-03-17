all:
	g++ -g -Wall -shared -o libmath-v1.so MathLibrary.cpp
	g++ -g -Wall -shared -o libmath-v2.so MathLibraryChanged.cpp
	g++ -g -Wall -o math-client MathClient.cpp -I . -L. libmath-v1.so

