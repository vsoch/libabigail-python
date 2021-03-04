// AbiSpack.cpp
// Functions for spack to interact with libabigail (or other ABI libraries)

#include <iostream>
#include <string>
#include <vector>
#include <fstream>
#include "abispack.hpp"
#include "abg-corpus.h"
#include "abg-config.h"
#include "abg-comp-filter.h"
#include "abg-suppression.h"
#include "abg-tools-utils.h"
#include "abg-reader.h"
#include "abg-writer.h"
#include "abg-dwarf-reader.h"

using std::ostream;
using std::ofstream;
using abigail::corpus_sptr;
using abigail::dwarf_reader::create_read_context;
using abigail::dwarf_reader::read_context;
using abigail::dwarf_reader::read_context_sptr;
using abigail::dwarf_reader::read_corpus_from_elf;
using abigail::dwarf_reader::status;
using abigail::ir::environment_sptr;
using abigail::tools_utils::get_library_version_string;
using abigail::tools_utils::temp_file;
using abigail::tools_utils::temp_file_sptr;
using abigail::xml_writer::create_write_context;
using abigail::xml_writer::write_context_sptr;
using abigail::xml_writer::write_corpus;


namespace abispack {

    std::string path;
    
    int Libabigail::HelloWorld() {
        return 0;
    }
      
    // Read an elf corpus and save to temporary file
    std::string Libabigail::ReadElfCorpus(std::string in_file_path, 
        bool load_all_types, 
        bool linux_kernel_mode)
    {

        // TODO: we need input validating here
        // Note sure what this is
        std::vector<char**> prepared_di_root_paths;
        
        // Create a new environment and context
        environment_sptr env(new abigail::ir::environment);
        read_context_sptr c = create_read_context(in_file_path,
            prepared_di_root_paths,
            env.get(),
            load_all_types,
            linux_kernel_mode);

        read_context& ctxt = *c;
        status s = abigail::dwarf_reader::STATUS_UNKNOWN;
        corpus_sptr corpus = read_corpus_from_elf(ctxt, s);

        // Create a write context and save to temporary file
        const write_context_sptr& write_ctxt = create_write_context(corpus->get_environment(), std::cout);
        temp_file_sptr tmp_file = temp_file::create();
        ofstream of(tmp_file->get_path(), std::ios_base::trunc);
        set_ostream(*write_ctxt, of);
        int exit_code = write_corpus(*write_ctxt, corpus, 0);
        of.close();
        std::cout << exit_code;
        return tmp_file->get_path();
    }
    
    int Libabigail::Load (std::string path) {
        path = path;
        // auto corpus = abigail::dwarf_reader::read_corpus_from_elf(path);
        return 0;
    }
    
    int Libabigail::GetVersion () {
        auto version = get_library_version_string();
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
