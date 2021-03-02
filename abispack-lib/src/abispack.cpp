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


// abg-ir.h
// abg-corpus.h

namespace abispack {

    std::string path;
    
    int Libabigail::HelloWorld() {
        return 0;
    }
      
    int Libabigail::Load (std::string path) {
        path = path;
        // auto corpus = abigail::dwarf_reader::read_corpus_from_elf(path);
        return 0;
    }
    
    int Libabigail::GetVersion () {
        auto version = abigail::tools_utils::get_library_version_string();
        std::cout << version + "\n";
        return 0;
    }

    void LoadParser(abispack::Libabigail& parser, std::string path) {
        parser.path = path;
    }
}


int main() {

    abispack::Libabigail parser;
    std::string path = "/usr/local/lib/libabigail.so";
    abispack::LoadParser(parser, path);
    std::cout << parser.path << "\n";
    return 0; 
}
