// abispack.h
#pragma once

#include <iostream>

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
    
    void Load(std::string path);
}
