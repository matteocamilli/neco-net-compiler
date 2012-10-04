""" CLI for neco check compiler.

This module provides a CLI for neco that supports python 2.7.

The loading of the module will raise a runtime error
if loaded with wrong python version.
"""

import sys
if (2, 7, 0) <= sys.version_info < (3, 0, 0) :
    VERSION = (2, 7)
else:
    raise RuntimeError("unsupported python version")

import argparse, os
import neco.config as config
from neco import g_logo

import cPickle as pickle

from neco import compile_checker
import core.xmlproperties

def exclusive(elts, acc=False):
    try:
        e = bool(elts.pop())
    except IndexError:
        return True
    
    if e and acc:
        return False
    else:
        return exclusive(elts, e ^ acc)

class Main(object):

    def __init__(self, progname='checkcli', logo=False, cli_args=None):

        print "{} uses python {}".format(progname, sys.version)

        if logo:
            print g_logo

        prog = os.path.basename(sys.argv[0])
        formula_meta = 'FORMULA'
        xml_formula_meta = 'XML_FILE'
        # parse arguments
        parser = argparse.ArgumentParser(progname,
                                         argument_default=argparse.SUPPRESS,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                         usage="{} [OPTIONS]".format(prog))

        parser.add_argument('--trace', '-t', default='trace', dest='trace', metavar='TRACEFILE', type=str,
                            help='compilation trace file')

        parser.add_argument('--profile', '-p', default='profile', dest='profile', action='store_true',
                            help='enable profiling.')

        parser.add_argument('--include', '-I', default=['.'], dest='includes', action='append', metavar='PATH',
                            help='additionnal search paths (libs, files).')

        parser.add_argument('--formula', metavar=formula_meta, type=str, help='formula', default="false")

        parser.add_argument('--xml', metavar=xml_formula_meta, default=None, dest='xml', type=str, help='xml formula file')

        if cli_args:
            args = parser.parse_args(cli_args)
        else:
            args = parser.parse_args()
        

        trace_file = args.trace
        profile = args.profile
        formula = args.formula
        xml_file = args.xml
        
        if formula and xml_file:
            raise RuntimeError
        
        trace_fd = open(trace_file)
        trace = pickle.load(trace_fd)
        model_file = trace['model']
        i = model_file.rfind('.')
        ext = model_file[i + 1:]
        name = model_file[:i]
        
        model, abcd, pnml = (None,) * 3
        if ext == 'py':
            model = name
        elif ext == 'abcd':
            abcd = name
        elif ext == 'pnml':
            pnml = name
        
        assert(exclusive([model, abcd, pnml]))
        
        net = None
        if pnml:
            import compilecli
            net = compilecli.load_pnml_file(pnml)
        elif model:
            import compilecli
            net = compilecli.load_snakes_net(model, 'net')
        assert(net)

        env_includes = os.environ['NECO_INCLUDE'].split(":")
        args.includes.extend(env_includes)

        if formula:
            formula = core.properties.PropertyParser().input(formula)
            
        elif xml_file:
            properties = core.xmlproperties.parse(xml_file)
            if not properties:
                print >> sys.stderr, "no property found in {}".format(xml_file)
                exit(1)
            elif len(properties) > 1:
                print >> sys.stderr, "neco can handle only one property at a time"
                exit(1)
            formula = properties[0].formula
        
        # setup config
        config.set(#debug = cli_argument_parser.debug(),
                   profile=profile,
                   backend='cython', # force cython
                   formula=formula,
                   trace_calls=False,
                   additional_search_paths=args.includes,
                   trace_file=trace_file)

        compile_checker(formula, net)

if __name__ == '__main__':
    Main()