# Specify extensions of files to delete when cleaning
CLEANEXTS   = o a 

# Specify the target file and the install directory
OUTPUTFILE  = bin/abispack
SRCFILES = src/abispack.cpp
INCLUDES = $(shell pkg-config --cflags-only-I libabigail)
CFLAGS = -g -Wall $(INCLUDES) $(shell pkg-config --cflags-only-other libabigail)
LDFLAGS = $(shell pkg-config --libs libabigail)

# Default target
.PHONY: all
all: $(OUTPUTFILE) $(OUTPUTFILE).o $(OUTPUTFILE).so

shroud:
	shroud abispack.yml --outdir-python abispack

# Build abispack.o from source files
$(OUTPUTFILE): $(SRCFILES)
	g++ -o $(OUTPUTFILE) -Iinclude $(SRCFILES) $(CFLAGS) $(LDFLAGS)

$(OUTPUTFILE).o: $(SRCFILES)
	g++ -c -o $(OUTPUTFILE).o -fPIC -Iinclude $(SRCFILES) $(CFLAGS) $(LDFLAGS)

$(OUTPUTFILE).so: $(OUTPUTFILE).o
	g++ -shared -o $(OUTPUTFILE).so $(OUTPUTFILE).o

.PHONY: clean 
clean:
	rm $(OUTPUTFILE) $(OUTPUTFILE).o $(OUTPUTFILE.so)
