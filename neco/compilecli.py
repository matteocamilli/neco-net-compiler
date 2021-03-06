""" CLI for neco compiler.

This module provides a CLI for neco that supports python 2.7.

The loading of the module will raise a runtime error
if loaded with wrong python version.
"""

from neco import compile_net, g_logo, produce_pnml_file, load_pnml_file, \
    load_snakes_net
from neco.utils import fatal_error
from time import time
import argparse
from neco.config import Config
import os
import sys
if (2, 7, 0) <= sys.version_info < (3, 0, 0) :
    VERSION = (2, 7)
else:
    raise RuntimeError("unsupported python version")

g_produced_files = ["*.pyc",
                    "net.so",
                    "net.pyx",
                    "net.pxd",
                    "net_api.h",
                    "net.h",
                    "net.c",
                    "net.py",
                    "net.pyc",
                    "net.pyo",
                    "ctypes.h",
                    "ctypes_ext.pxd",
                    "trace"]
class Main(object):

    _instance_ = None    # unique instance

    def __init__(self, progname = 'compilecli', logo = False, cli_args = None):

        print "{} uses python {}".format(progname, sys.version)
        assert(not self.__class__._instance_)    # assert called only once
        self.__class__._instance_ = self    # setup the unique instance

        if logo:
            print g_logo

        # parse arguments

        parser = argparse.ArgumentParser(progname,
                                         argument_default = argparse.SUPPRESS,
                                         formatter_class = argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--lang', '-l', default = 'python', dest = 'language', choices = ['python', 'cython'],
                            help = 'set target language')

        model_group = parser.add_argument_group('Model related options')
        model_group.add_argument('--abcd', dest = 'abcd', default = None, metavar = 'FILE', type = str,
                                 help = 'ABCD file to be compiled')
        model_group.add_argument('--pnml', dest = 'pnml', default = None, metavar = 'FILE', type = str,
                                 help = 'ABCD file to be compiled ( or produced if used with --abcd )')
        model_group.add_argument('--module', '-m', default = None, dest = 'module', metavar = 'MODULE', type = str,
                                 help = 'Python module containing the Petri net to be compiled')
        model_group.add_argument('--netvar', '-v', default = 'net', dest = 'netvar', metavar = 'VARIABLE', type = str,
                                 help = 'Variable holding the Petri net')
        model_group.add_argument('--import', '-i', default = [], dest = 'imports', action = 'append',
                                 help = 'add additional files to be imported')

        optimize_group = parser.add_argument_group('Optimizations')
        optimize_group.add_argument('--optimize', '-O', default = False, dest = 'optimize', action = 'store_true',
                                    help = 'enable optimizations.')
        optimize_group.add_argument('--optimize-pack', '-Op', default = False, dest = 'bit_packing', action = 'store_true',
                                    help = 'enable bit packing. [cython only]')
        optimize_group.add_argument('--optimize-flow', '-Of', default = False, dest = 'optimize_flow', action = 'store_true',
                                    help = 'enable flow control optimizations.')

        pid_group = parser.add_argument_group('Dynamic process creation')
        pid_group.add_argument('--detect-pid-symmetries', '-dps', default = False, dest = 'detect_pid_symmetries', action = 'store_true',
                               help = 'enable reductions by symmetries.')
        pid_group.add_argument('--pid-parent', '-pp', default = True, dest = 'pid_parent', action = 'store_true',
                               help = 'preserve parent relation.')
        pid_group.add_argument('--pid-sibling', '-ps', default = False, dest = 'pid_sibling', action = 'store_true',
                               help = 'preserve sibling relation. [not implemented yet]')
        pid_group.add_argument('--normalize-only', '-no', default = False, dest = 'normalize_only', action = 'store_true',
                               help = 'optimistic approach, order trees but do not perform permutations.')
        pid_group.add_argument('--pid-first', '-pf', default = False, dest = 'pid_first', action = 'store_true',
                               help = 'use pid-first restriction, ie., pids are tuple first components. Pid-tree reordering yield normal forms.')

        print_group = parser.add_argument_group('Printing and profiling')
        print_group.add_argument('--profile', '-p', default = False, dest = 'profile', action = 'store_true',
                                 help = 'enable profiling support')
        print_group.add_argument('--no-stats', default = False, dest = 'no_stats', action = 'store_true',
                                 help = 'disable dynamic stats (transitions/sec, etc.)')

        other_group = parser.add_argument_group('Cython specific options')
        other_group.add_argument('--trace', '-t', default = 'trace', dest = 'trace', metavar = 'TRACEFILE', type = str,
                                 help = 'setup trace file name, trace files are used by neco-check.')
        other_group.add_argument('--include', '-I', default = [], dest = 'includes', action = 'append',
                                 help = 'additional include paths.')

        if cli_args:
            args = parser.parse_args(cli_args)
        else:
            args = parser.parse_args()

        # retrieve arguments
        abcd = args.abcd
        pnml = args.pnml
        module = args.module
        netvar = args.netvar
        profile = args.profile
        trace = args.trace

        self.abcd = abcd
        self.pnml = pnml
        self.module = module
        self.netvar = args.netvar
        self.profile = profile
        model_file = None

        if args.optimize_flow:
            args.optimize = True

        try:
            env_includes = os.environ['NECO_INCLUDE'].split(":")
        except KeyError:
            env_includes = []

        args.includes.extend(env_includes)

        try:
            if module and module[-3:] == '.py':
                module = module[:-3]
        except IndexError:
            pass

        # checks for conflicts in options
        if module:
            model_file = module + '.py'
            if abcd:
                fatal_error("A snakes module cannot be used with an abcd file.")
            elif pnml:
                fatal_error("A snakes module cannot be used with a pnml file.")

        elif abcd:
            model_file = abcd
        elif pnml:
            model_file = pnml

        # setup config
        self.config = Config()
        self.config.set_options(optimize = args.optimize,
                                bit_packing = args.bit_packing,
                                backend = args.language,
                                profile = args.profile,
                                imports = args.imports,
                                no_stats = args.no_stats,
                                optimize_flow = args.optimize_flow,
                                search_paths = args.includes,
                                trace_calls = False,
                                trace_file = trace,
                                normalize_pids = args.detect_pid_symmetries,
                                pid_parent = args.pid_parent,
                                pid_sibling = args.pid_sibling,
                                normalize_only = args.normalize_only,
                                pid_first = args.pid_first,
                                model = model_file)

        # retrieve the Petri net from abcd file (produces a pnml file)
        remove_pnml = not pnml
        if abcd:
            pnml = produce_pnml_file(abcd, pnml)

        # retrieve the Petri net from pnml file
        if pnml:
            petri_net = load_pnml_file(pnml, remove_pnml)

        # retrieve the Petri net from module
        else:
            if not module:
                module = 'spec'
            if not netvar:
                netvar = 'net'

            petri_net = load_snakes_net(module, netvar)

        self.petri_net = petri_net

        if profile:
            # produce compiler trace
            import cProfile
            cProfile.run('neco.compilecli.Main._instance_.compile()', 'compile.prof')

        else:    # without profiler
            self.compile()

    def compile(self):
        """ Compile the model. """
        for f in g_produced_files:
            try:   os.remove(f)
            except OSError: pass    # ignore errors

        start = time()
        compiled_net = compile_net(net = self.petri_net, config = self.config)
        end = time()

        if not compiled_net:
            print "Error during compilation."
            exit(-1)
        print "compilation time: ", end - start
        return end - start

if __name__ == '__main__':
    Main('compilecli')
