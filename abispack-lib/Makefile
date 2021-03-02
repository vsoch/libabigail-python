# Specify extensions of files to delete when cleaning
CLEANEXTS   = o a 

# Specify the target file and the install directory
OUTPUTFILE  = abispack.o
SRCFILES = src/abispack.cpp
INCLUDES = -I/libabigail-1.8/include
CFLAGS = -g -Wall $(INCLUDES)

# Default target
.PHONY: all
all: $(OUTPUTFILE)

# Build abispack.o from source files
$(OUTPUTFILE): $(SRCFILES)
	g++ -o $(OUTPUTFILE) -Iinclude $(SRCFILES) $(CFLAGS)

.PHONY: clean 
clean:
	rm $(OUTPUTFILE)
