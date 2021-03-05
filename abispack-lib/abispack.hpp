// abispack.h
#pragma once

#include <iostream>
#include <string>
#include <vector>
#include "abg-corpus.h"

using abigail::corpus_sptr;

namespace abispack
{
    class Libabigail
    {
    public:
        std::string path;
        static int HelloWorld();
        static int Load (std::string path);
        static int GetVersion ();
        static std::string ReadElfCorpusAndWriteXML(std::string in_file_path, 
            std::string out_file_path,
            bool load_all_types = true, 
            bool linux_kernel_mode = false);
    };
    
    int WriteCorpus(corpus_sptr corpus, std::string out_file_path);
}
