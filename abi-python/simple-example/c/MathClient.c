// MathClient.cpp
// compile with: cl /EHsc MathClient.cpp /link MathLibrary.lib

#include <stdio.h>
#include "MathLibrary.h"

int main()
{
    double a = 7.4;
    int b = 99;

    printf("%f\n", Add(a, (double)b));
    return 0;
}
