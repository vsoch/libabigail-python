#!/usr/bin/env python

# The abi_parser.py is a simple script to use abidw (or other libabigail 
# executables) to retrieve output and then parse in Python. Running some of
# these commands natively for large libraries are fairly slow, so I'd expect
# the parsing to be slower at best :)

import os
import json
import shutil
import subprocess
import sys
import threading
import xmltodict


class LibabigailWrapper:
    """A Libabigail Wrapper exists only to provide function wrappers around
    the set of Libabigail tools. We only expose to the user functions based
    on the binaries for libabigail that are discovered. Currently, we care
    about abicompat  abidiff  abidw  abilint  abipkgdiff, and not kmidiff
    Example Usage:
        cli = LibabigailWrapper()
        cli.abidw("/usr/local/lib/libabigail.so")        
    """
    def __init__(self):       
        self._find_tools()  

    def __str__(self):
        return "[libabigail-tools|%s]" % ",".join(self.tools)

    def __repr__(self):
        return str(self)

    def abidw(self, library):
        """A wrapper for abidw. Requires input of an existing binary to parse
        """
        if not os.path.exists(library):
            sys.exit("%s does not exist." % library)
        runner = self.run_tool("abidw", library)
        # This could probably be streamed on reading, but seems to work on
        return xmltodict.parse("\n".join(runner.output))

    def abidiff(self):
        print("not written")
        
    def abicompat(self):
        print("not written")
        
    def abilint(self):
        print("not written")

    def abipkgdiff(self):
        print("not written")

    def run_tool(self, tool, *args):
        """A general runner to run a command, and return the runner with output
        and error to parse The user should pass ordered arguments as args.
        """
        runner = CommandRunner()
        runner.run_command([self._wrapped[tool], *args])
        return runner
    
    def save_json(self, obj, filename):
        with open(filename, 'w') as fd:
            fd.writelines(json.dumps(obj, indent=4))
        return filename

    @property
    def tools(self):
        """Show what tools are available
        """
        return list(self._wrapped.keys())
          
    def _find_tools(self):

        tools = ["abicompat", "abidiff", "abidw", "abilint", "abipkgdiff"]

        # We will keep a record of the tools that are wrapped
        self._wrapped = {}
        for tool in tools:
            if (path := self._exists(tool)):
                self._wrapped[tool] = path
            # Remove the function if we don't have the executable
            else:
                delattr(self, tool)
                        
    def _exists(self, name):
        """If a library exists, return the path. Otherwise, None
        """
        if (path := shutil.which(name)):
            return path

        
class CommandRunner(object):
    """This is a CommandRunner that is derived from the one I wrote for caliper
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.error = []
        self.output = []
        self.retval = None

    def reader(self, stream, context):
        # Make sure we save to the correct field
        lines = self.error
        if context == "stdout":
            lines = self.output

        while True:
            s = stream.readline()
            if not s:
                break
            lines.append(s.decode("utf-8"))
        stream.close()

    def run_command(self, cmd, env=None, **kwargs):
        self.reset()

        # Preview the command for the uesr
        print(" ".join(cmd))

        # If we need to update the environment
        # **IMPORTANT: this will include envars from host!)**
        envars = os.environ.copy()
        if env:
            envars.update(env)

        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=envars, **kwargs
        )

        # Create threads for error and output
        t1 = threading.Thread(target=self.reader, args=(p.stdout, "stdout"))
        t1.start()
        t2 = threading.Thread(target=self.reader, args=(p.stderr, "stderr"))
        t2.start()

        p.wait()
        t1.join()
        t2.join()
        self.retval = p.returncode
        return self.output


if __name__ == '__main__':
    pass
