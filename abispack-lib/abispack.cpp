// AbiSpack.cpp
// Functions for spack to interact with libabigail (or other ABI libraries)

#include <iostream>
#include <string>
#include <vector>
#include "abispack.hpp"
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
      
    int Libabigail::ReadElfCorpus(std::string in_file_path, 
        bool load_all_types, 
        bool linux_kernel_mode)
    {

        // Note sure what this is
        std::vector<char**> prepared_di_root_paths;
        
        // Create a new environment and context
        abigail::ir::environment_sptr env(new abigail::ir::environment);
        abigail::dwarf_reader::read_context_sptr c = abigail::dwarf_reader::create_read_context(in_file_path,
            prepared_di_root_paths,
            env.get(),
            load_all_types,
            linux_kernel_mode);

        abigail::dwarf_reader::read_context& ctxt = *c;
        abigail::dwarf_reader::status s = abigail::dwarf_reader::STATUS_UNKNOWN;
        abigail::corpus_sptr corpus = abigail::dwarf_reader::read_corpus_from_elf(ctxt, s);
        //std::cout << corpus;
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
