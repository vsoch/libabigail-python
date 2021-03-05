#!/usr/bin/env python3

# In this script, we load in a libabigail export that is converted to json
# via https://github.com/vsoch/libabigail-python/tree/main/wrapper, and
# then "flatten" it into features that are intended to be used in some ML,
# predictive framework.

import os
import json
import sys
import lddwrap
import jsonschema
import pathlib

from abi_parser import LibabigailWrapper

schema = {
  "$id": "https://github.com/vsoch/libabigail-python",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "A schema to parse corpus exported from libabigail in json",
  "type": "object",
  "required": ["abi-corpus"],
  "properties": {
    "abi-corpus": {
      "type": "object",
      "required": ["@path", "@architecture", "@soname"],
      "properties": {
        "@path": {"type": "string"},
        "@architecture": {"type": "string"},
        "@soname": {"type": "string"},
        "elf-needed": {
          "type": "object",
          "required": ["dependency"],
          "properties": {
            "dependency": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["@name"],
                "properties": {"@name": {"type": "string"}},
               },
            }
          },
        },
        "elf-function-symbols": {
          "type": "object",
          "required": ["elf-symbol"],
          "properties": {
            "elf-symbol": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["@name", "@type", "@binding", "@visibility", "@is-defined"],
                "properties": {
                  "@name": {"type": "string"},
                  "@type": {"type": "string"},
                  "@binding": {"type": "string"},
                  "@visibility": {"type": "string"},
                  "@is-defined": {"type": "string"},
                },
              },
            }
          },
        },
        "elf-variable-symbols": {
          "type": "object",
          "required": ["elf-symbol"],
          "properties": {
            "elf-symbol": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["@name", "@size", "@type", "@binding", "@visibility", "@is-defined"],
                "properties": {
                  "@name": {"type": "string"},
                  "@size": {"type": "string"},
                  "@type": {"type": "string"},
                  "@binding": {"type": "string"},
                  "@visibility": {"type": "string"},
                  "@is-defined": {"type": "string"},
                  "@alias": {"type": "string"},
                },
              },
            }
          }                      
        },
        "abi-instr": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ['@version', '@address-size', '@path', '@comp-dir-path', "@language"],
                "properties": {
                  "@version": {"type": "string"},
                  "@language": {"type": "string"},
                  "@address-size": {"type": "string"},
                  "@path": {"type": "string"},
                  "@comp-dir-path": {"type": "string"},

                  # TODO: these aren't defined here yet
                  "reference-type-def": {},
                  "namespace-decl": {},
                  "type-decl": {},
                  "pointer-type-def": {},
                  "qualified-type-def": {},                  
                  "typedef-decl": {},
                  "array-type-def": {},
                  "class-decl": {},
                  "union-decl": {},
                  "enum-decl": {},
                },
              }
            }
         }
      }
    }
}

def extract_abi(library_name, json_file):
    """Use the abi wrapper to write ABI to file
    """
    # Create the abi parser for each dependency   
    cli = LibabigailWrapper()

    # Use abidw as a proxy for getting what we need?
    abi_dict = cli.abidw(library_name)
    cli.save_json(abi_dict, json_file)


def read_json(filename):
    with open(filename, "r") as fd:
        raw = json.loads(fd.read())
    return raw
    

def write_library(library_name):
    """Given a json file export for a library of interest, parse it into a smaller
    corpus that we can test to see if looking at has vs. needs is sufficient
    to determine compatability
    """
    path = pathlib.Path(library_name)  
    if not path.exists():
        sys.exit("%s does not exist." % path)
    
    # If the extracted json doesn't exist, create it
    json_file = "%s.json" % os.path.basename(library_name).split('.')[0]
    if not os.path.exists(json_file):
        extract_abi(library_name, json_file)

    # If we already have the output, read and return it
    output_file, ext = os.path.splitext(json_file)
    output_file = "%s-library.json" % output_file
    if os.path.exists(output_file):
        return read_json(output_file)
    
    # Read it to prepare
    raw = read_json(json_file)

    # validate structure of corpus
    # see above, we need to add structures for different type defs
    # if not jsonschema.validate(schema=schema, instance=raw):
    #    sys.exit("Not valid json, see the schema in this file.")

    # Get unique values for types
    uniques = {}

    # Elf function symbols
    for elf_symbol in raw['abi-corpus'].get('elf-function-symbols', {}).get('elf-symbol', {}):
        for attribute, value in elf_symbol.items():
            if attribute in ["@name", "@alias"]:
                continue
            key = "elf-function-symbol_%s" % attribute
            if key not in uniques:
                uniques[key] = set()
            uniques[key].add(value)
            
    # Elf variable symbols
    for elf_symbol in raw['abi-corpus'].get('elf-variable-symbols', {}).get('elf-symbol', {}):
        if isinstance(elf_symbol, str):
            continue
        for attribute, value in elf_symbol.items():
            if attribute in ["@name", "@alias", "@size"]:
                continue
            key = "elf-variable-symbol_%s" % attribute
            if key not in uniques:
                uniques[key] = set()
            uniques[key].add(value)

    # Abi attributes
    for group in raw['abi-corpus'].get('abi-instr', {}):
        for attribute, values in group.items():
            if attribute.startswith("@"):
                key = "abi-instr_%s" % attribute
                if key not in uniques:
                    uniques[key] = set()
                uniques[key].add(value)
                continue

    def add_class_item(subgroup_key, subgroup_items):
        if subgroup_key != "class-decl":
            return
        library[subgroup_key] += subgroup_items.get('member-function', [])
        library[subgroup_key] += subgroup_items.get('data-member', [])

    def parse_namespace(values):
        for subgroup in values:
            if isinstance(subgroup, str):
                continue
            for subgroup_key, subgroup_items in subgroup.items():
                if subgroup_key in ['@name']:
                    continue

                if subgroup_key not in library:
                        library[subgroup_key] = []  
                if subgroup_key in ['function-decl']:
                    library[subgroup_key] += subgroup_items                        
                elif subgroup_key == "typedef-decl":
                    if isinstance(subgroup_items, dict):
                        subgroup_items = [subgroup_items]
                    library[subgroup_key] += subgroup_items
                elif subgroup_key == 'class-decl':
                    if isinstance(subgroup_items, list):
                        for subclass_group in subgroup_items:
                            for subclass_key, subclass_items in subclass_group.items():
                                add_class_item(subclass_key, subclass_items)
                    else:
                        add_class_item(subgroup_key, subgroup_items)
                elif subgroup_key == 'namespace-decl':
                    parse_namespace(subgroup_items)
                else:
                    print("Subgroup %s not supported." % subgroup_key)

    # Try to make a list of "has" and "needs"
    library = {}
    for group in raw['abi-corpus'].get('abi-instr', {}):
        for attribute, values in group.items():
            if attribute.startswith("@"):
                key = "abi-instr_%s" % attribute
                if key not in uniques:
                    uniques[key] = set()
                uniques[key].add(value)
                continue
         
            if attribute in ['array-type-def']:
                continue
                
            if attribute in ["function-type-def", "typedef-decl", "class-decl"]:
                if attribute not in library:
                    library[attribute] = []
                library[attribute] += values

            if attribute in ['namespace-decl']:
                parse_namespace(values)
  
            if attribute in library and not library[attribute]:
                del library[attribute]

    library['elf-needed'] = raw['abi-corpus'].get('elf-needed', {})
    output_file, ext = os.path.splitext(json_file)
    output_file = "%s-library.json" % output_file
    with open(output_file, "w") as fd:
        fd.writelines(json.dumps(library, indent=3))
    return library


def main(library_name):

    # first write the library for libabigail (or the main one)
    library = write_library(library_name)
    dependencies = {}

    # Get the dependencies for it
    path = pathlib.Path(library_name)
    deps = lddwrap.list_dependencies(path=path, env={"LD_LIBRARY_PATH": "/usr/local/lib"})
    for dep in deps:
        if not dep.path:
            continue
        dependencies[str(dep.path)] = write_library(str(dep.path))

    # Create list of what libabigail needs
    # probably a bug, some of these are strings
    needs = [x for x in library['function-decl'] if not isinstance(x, str) and ("abigail" not in x.get('@elf-symbol-id', "") and "abigail" not in x.get("@mangled-name", "") and "abigail" not in x.get("@filepath", ""))]
    mangled_names = [x['@mangled-name'] for x in needs]    

    # TODO not sure how to compare here, we only have elf symbols from the other ones
    # Get what is provided
    

if __name__ == "__main__":
    if len(sys.argv) < 1:
        sys.exit("Please provide an input json to parse.")
    library_name = sys.argv[1]
    main(library_name)
