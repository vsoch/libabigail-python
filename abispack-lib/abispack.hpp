// abispack.h
#pragma once

#include <iostream>
#include <string>
#include <vector>

namespace abispack
{
    class Libabigail
    {
    public:
        std::string path;
        static int HelloWorld();
        static int Load (std::string path);
        static int GetVersion ();
        static int ReadElfCorpus(std::string in_file_path, 
            bool load_all_types = true, 
            bool linux_kernel_mode = false);
    };
    
    void LoadParser(Libabigail& parser, std::string path);
}
