// abispack.h
#pragma once

#include <iostream>
#include <string>

namespace abispack
{
    class Libabigail
    {
    public:
        std::string path;
        static int HelloWorld();
        static int Load (std::string path);
        static int GetVersion ();
    };
    
    void LoadParser(Libabigail& parser, std::string path);
}
