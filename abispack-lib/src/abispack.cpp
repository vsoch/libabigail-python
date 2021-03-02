// AbiSpack.cpp
// Functions for spack to interact with libabigail (or other ABI libraries)

#include <iostream>
#include "abispack.h"
#include "abg-corpus.h"
#include "abg-config.h"
#include "abg-comp-filter.h"
#include "abg-suppression.h"
#include "abg-tools-utils.h"
#include "abg-reader.h"
#include "abg-dwarf-reader.h"

using abigail::xml_reader::read_corpus_from_file;

// abg-ir.h
// abg-corpus.h

using namespace std;

namespace abispack
{
    int Libabigail::HelloWorld()
    {
        cout << "Hello World!";
        string path = "/usr/local/lib/libabigail.so";
        auto corpus = abigail::xml_reader::read_corpus_from_file(path);
        return 0; 
    }
}

int main() {
    return 0;
}
