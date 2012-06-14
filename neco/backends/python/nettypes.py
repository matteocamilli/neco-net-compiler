""" Python basic net types. """

from neco.utils import should_not_be_called, todo
import neco.utils as utils
import neco.core.nettypes as coretypes
from pyast import Builder, E, A, stmt
from neco.core.info import *

import pyast as ast

GENERATOR_PLACE = 'sgen'

neco_stubs = {
    'object_place_type_update_pids'     : 'data.neco__multiset_update_pids',
    'object_place_type_update_pid_tree' : 'data.neco__iterable_update_pid_tree',
    'create_pid_tree'    : 'data.neco__create_pid_tree',
    'normalize_pid_tree' : 'data.neco__normalize_pid_tree',
    'generator_place_update_pids'     : 'data.neco__generator_token_transformer',
    'generator_place_update_pid_tree' : 'data.neco__generator_multiset_update_pid_tree',
}

################################################################################

def type2str(type):
    """ Type to string translation.

    @param type: type to translate
    @type type: C{TypeInfo}
    """
    if type.is_UserType:
        if type.is_BlackToken:
            return "BlackToken"
        elif type.is_Bool:
            return "bool"
        elif type.is_Int:
            return "int"
        elif type.is_String:
            return "str"
        else:
            return str(type)
    elif type.is_TupleType:
        return "tuple"
    else:
        return "object"

TypeInfo.register_type("Multiset")

################################################################################

class PythonPlaceType(object):
    """ Base class for python backend place types. """
     
    allow_pids = False

    def place_expr(self, env, marking_var):
        return self.marking_type.gen_get_place(env,
                                               marking_var = marking_var,
                                               place_name = self.info.name,
                                               mutable = False)
        
    @property
    def is_ProcessPlace(self):
        return False

################################################################################

# multiple inheritance is used to allow type matching.

class ObjectPlaceType(coretypes.ObjectPlaceType, PythonPlaceType):
    """ Python implementation of the fallback place type. """
    
    allow_pids = True
    
    def __init__(self, place_info, marking_type):
        coretypes.ObjectPlaceType.__init__(self,
                                           place_info = place_info,
                                           marking_type = marking_type,
                                           type = TypeInfo.MultiSet,
                                           token_type = place_info.type)
        
    def new_place_expr(self, env):
        return E("multiset([])")

    def size_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return E('len').call([E(place_expr)])

    def iterable_expr(self, env, marking_var):
        return self.place_expr(env, marking_var)

    def remove_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return stmt( ast.Call(func=ast.Attribute(value=place_expr,
                                                 attr="remove"),
                              args=[compiled_token]
                              )
                     )

    def add_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return stmt( ast.Call(func=ast.Attribute(value=place_expr,
                                                 attr="add"),
                              args=[compiled_token]) )

    def token_expr(self, env, value):
        return E(repr(value))

    def copy_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.Call(func=ast.Attribute(value=place_expr,
                                           attr="copy"
                                           )
                        )

    def clear_stmt(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return stmt( ast.Assign(targets=[place_expr],
                                value=ast.Call(func=ast.Name(id="multiset")))
                     )

    def not_empty_expr(self, env, marking_var):
        return self.place_expr(env, marking_var)


    def add_multiset_stmt(self, env, multiset, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return stmt( ast.Call(func=ast.Attribute(name=place_expr,
                                                 attr='update'),
                              args=[multiset])
                     )

    def add_items_stmt(self, env, multiset, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return stmt( ast.Call(func=ast.Attribute(value=place_expr,
                                                 attr='add_items'),
                              args=[multiset])
                     )

    def dump_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.Call(func=ast.Attribute(value=place_expr,
                                           attr='__dump__'))

    def update_pids_stmt(self, env, marking_var, new_pid_dict_var):
        stub_name = neco_stubs['object_place_type_update_pids']
        return ast.Assign(targets=[self.place_expr(env, marking_var)],
                          value=ast.Call(func=ast.Name(stub_name),
                                         args=[self.place_expr(self, marking_var),
                                               ast.Name(new_pid_dict_var.name)]))
    
    def update_pid_tree(self, env, marking_var, pid_tree_var):
        stub_name = neco_stubs['object_place_type_update_pid_tree']
        return stmt(ast.Call(func=ast.Name(stub_name),
                             args=[self.place_expr(self, marking_var),
                                   ast.Name(pid_tree_var.name)]))

################################################################################

class StaticMarkingType(coretypes.MarkingType):
    """ Python marking type implementation, places as class attributes. """

    def __init__(self):
        coretypes.MarkingType.__init__(self,
                                       TypeInfo.register_type('Marking'),
                                       TypeInfo.register_type('set'))
        self.id_provider = utils.NameProvider()
        self._process_place_types = {}

    def __str__(self):
        s = []
        s.append('Marking:')
        for name, place_type in self.place_types.iteritems():
            s.append('{} : {}'.format(name, place_type.__class__))
        s.append('End')
        return '\n'.join(s)
    
    def gen_types(self):
        """ Build place types using C{select_type} predicate.
        """
        opt = config.get('optimize')
        for place_info in self.flow_control_places:
            try:
                self._process_place_types[place_info.process_name].add_place(place_info)
            except KeyError:
                new_id = place_info.process_name
                place_type = FlowPlaceType(place_info = PlaceInfo.Dummy(new_id,
                                                                        process_name = place_info.process_name),
                                           marking_type = self)
                self.place_types[place_info.process_name] = place_type
                place_type.add_place(place_info)
                self._process_place_types[place_info.process_name] = place_type

        for place_info in self.one_safe_places:
            place_name = place_info.name

            if opt:
                if place_info.one_safe:
                    if place_info.type.is_BlackToken:
                        place_type = BTOneSafePlaceType(place_info, marking_type = self)
                    else:
                        place_type = OneSafePlaceType(place_info, marking_type = self)

                elif place_info.type.is_BlackToken:
                    place_type = BTPlaceType(place_info, marking_type = self)
                else:
                    place_type = ObjectPlaceType(place_info, marking_type = self)
            else:
                place_type = ObjectPlaceType(place_info, marking_type = self)

            if self.place_types.has_key(place_name):
                raise RuntimeError("{name} place exists".format(name=place_name))
            else:
                self.place_types[place_name] = place_type

        for place_info in self.places:
            place_name = place_info.name
            
            if place_info.type.is_BlackToken:
                place_type = BTPlaceType(place_info, marking_type = self)
            else:
                place_type = ObjectPlaceType(place_info, marking_type = self)

            if self.place_types.has_key(place_name):
                raise RuntimeError("{name} place exists".format(name=place_name))
            else:
                self.place_types[place_name] = place_type

    def new_marking_expr(self, env, *args):
        return E("Marking()")

    def gen_init_method(self, env):
        function = ast.FunctionDef(name='__init__',
                                   args=A('self').param('alloc', default='True').ast())

        if_block = ast.If(test=ast.Name(id='alloc'))

        for name, place_type in self.place_types.iteritems():
            if_block.body.append( ast.Assign(targets=[ast.Attribute(value=ast.Name(id='self'),
                                                                    attr=self.id_provider.get(name))],
                                             value=place_type.new_place_expr(env)) )
        function.body = if_block
        return function

    def gen_update_pids(self, env):
        vp = VariableProvider()
        self_var = vp.new_variable(self.type, name='self')
        new_pid_dict_var = vp.new_variable(self.type, name='new_pid_dict')

        function = ast.FunctionDef(name='update_pids',
                                   args=A(self_var.name).param(new_pid_dict_var.name).ast())
            
        body = []
        for place_type in self.place_types.itervalues():
            print place_type
            if not place_type.allow_pids:
                continue
            body.append( place_type.update_pids_stmt(env, self_var, new_pid_dict_var) )
        
        if not body:
            body = [ast.Pass()]
        
        function.body = body
        return function
    
    def gen_normalize_pids(self, env):
        vp = VariableProvider()
        self_var = vp.new_variable(self.type, name='self')
        tree_var = vp.new_variable(TypeInfo.AnyType,  name='tree')
        pid_dict_var = vp.new_variable(TypeInfo.Dict, name='pid_dict')
        
        function = ast.FunctionDef(name='normalize_pids',
                                   args=A(self_var.name).ast())
        body = []
        body.append(ast.Assign(targets=[ast.Name(id=tree_var.name)],
                               value=ast.Call(func=ast.Name(neco_stubs['create_pid_tree']),
                                              args=[])))
        # build the tree
        for name, place_type in self.place_types.iteritems():
            if not place_type.allow_pids:
                continue
            
            if name == GENERATOR_PLACE:
                body.append(stmt(ast.Call(func=ast.Name(neco_stubs['generator_place_update_pid_tree']),
                                          args=[ place_type.place_expr(env, self_var), ast.Name(id=tree_var.name) ] )))
            else:
                body.append(place_type.update_pid_tree(env, self_var, tree_var))
        # normalize tree and get dict
        body.append(ast.Assign(targets=[ast.Name(id=pid_dict_var.name)],
                               value=ast.Call(func=ast.Name(neco_stubs['normalize_pid_tree']),
                                              args=[ast.Name(tree_var.name)])))
        # update tokens with new pids
        for name, place_type in self.place_types.iteritems():
            if not place_type.allow_pids:
                continue
            
            if name == GENERATOR_PLACE:
                body.append( ast.Assign(targets=[ place_type.place_expr(env, self_var) ],
                                        value=ast.Call(func=ast.Name(neco_stubs['generator_place_update_pids']),
                                                       args=[place_type.place_expr(env, self_var),
                                                             ast.Name(pid_dict_var.name)]) ) )
            else:
                body.append( place_type.update_pids_stmt(env, self_var, pid_dict_var) )
           
        if not body:
            body = [ast.Pass()]
        
        function.body = body
        return function
            
    def normalize_marking_call(self, env, marking_var):
        return stmt(ast.Call(func=ast.Attribute(value=ast.Name(id=marking_var.name),
                                           attr='normalize_pids'),
                             args = []))

    def gen_copy_method(self, env):
        vp = VariableProvider()
        self_var = vp.new_variable(self.type, name='self')
        marking_var = vp.new_variable(self.type)

        function = ast.FunctionDef(name='copy',
                                   args=A(self_var.name).param('alloc', default='True').ast())

        tmp = [ ast.Assign(targets=[ast.Name(id=marking_var.name)],
                           value=E('Marking(False)')) ]

        for name, place_type in self.place_types.iteritems():
            tmp.append( ast.Assign(targets=[ast.Attribute(value=ast.Name(id = marking_var.name),
                                                          attr=self.id_provider.get(name))],
                                   value=place_type.copy_expr(env, marking_var = self_var))
                        )
        tmp.append(ast.Return(ast.Name(id=marking_var.name)))
        function.body = tmp
        return function

    def gen_eq_method(self, env):
        other = 'other'
        function = ast.FunctionDef(name='__eq__',
                                   args=A('self').param(other).ast())
        return_str = "return ("
        for i, (name, place_type) in enumerate(self.place_types.iteritems()):
            if name == GENERATOR_PLACE and config.get('pid_normalization'):
                continue
            
            id_name = self.id_provider.get(name)
            if i > 0:
                return_str += " and "
            return_str += "(self.%s == %s.%s)" % (id_name, other, id_name)
        return_str += ")"

        function.body = [ E(return_str) ]
        return function

    def gen_hash_method(self, env):
        builder = Builder()
        builder.begin_FunctionDef( name = '__hash__', args = A("self").ast() )
        builder.emit( E('h = 0') )

        for name, place_type in self.place_types.iteritems():
            if name == GENERATOR_PLACE and config.get('pid_normalization'):
                continue
            
            magic = hash(name)
            builder.emit( E('h ^= hash(self.' + self.id_provider.get(name) + ') ^ ' + str(magic)) )

        builder.emit_Return(E("h"))
        builder.end_FunctionDef()
        return builder.ast()

    def free_marking_stmt(self, env, marking_var, *args):
        pass

    def gen_repr_method(self, env):
        items = list(self.place_types.iteritems())
        items.sort(lambda (n1, t1), (n2, t2) : cmp(n1, n2))

        builder = Builder()
        builder.begin_FunctionDef( name = "__repr__", args = A("self").ast() )

        builder.emit( E('s = "hdict({"') )
        for (i, (place_name, place_type)) in enumerate(items):
            tmp = ',\n ' if i > 0 else ''
            builder.emit(ast.AugAssign(target=ast.Name(id='s'),
                                       op=ast.Add(),
                                       value=ast.BinOp(left=ast.Str(s = tmp + "'" + place_name + "' : "),
                                                       op=ast.Add(),
                                                       right=E('repr(self.' + self.id_provider.get(place_name) + ')')
                                                       )
                                       )
                         )
        builder.emit( E('s += "})"') )
        builder.emit_Return(E('s'))

        builder.end_FunctionDef()
        return builder.ast()

    def gen_dump_method(self, env):
        items = list(self.place_types.iteritems())
        items.sort(lambda (n1, t1), (n2, t2) : cmp(n1, n2))

        vp = VariableProvider()
        self_var = vp.new_variable(self.type, name='self')
        list_var = vp.new_variable()

        builder = Builder()
        builder.begin_FunctionDef( name = "__dump__", args = A(self_var.name).ast() )

        builder.emit( E('%s = ["{"]' % list_var.name) )
        for (i, (place_name, place_type)) in enumerate(items):
            if place_type.is_ProcessPlace:
                builder.emit( place_type.dump_expr(env, self_var, list_var) )
            else:
                builder.emit(stmt(ast.Call(func=E('{}.append'.format(list_var.name)),
                                           args=[ ast.BinOp(left = ast.Str(s = repr(place_name) + " : "),
                                                            op = ast.Add(),
                                                            right = ast.BinOp(left = place_type.dump_expr(env, self_var),
                                                                              op = ast.Add(),
                                                                              right = ast.Str(', '))
                                                            ) ]
                                           )
                                  )
                             )

        builder.emit(stmt(E('%s.append("}")' % list_var.name)))
        builder.emit_Return(E('"\\n".join({})'.format(list_var.name)))

        builder.end_FunctionDef()
        return builder.ast()

    def gen_api(self, env):
        cls = ast.ClassDef('Marking', bases=[ast.Name(id='object')])

        elts = []
        for name, place_type in self.place_types.iteritems():
            elts.append( ast.Str(self.id_provider.get(name)) )

        slots = ast.Assign(targets = [ast.Name('__slots__')],
                           value = ast.Tuple(elts))

        cls.body = [slots,
                    self.gen_init_method(env),
                    self.gen_repr_method(env),
                    self.gen_eq_method(env),
                    self.gen_hash_method(env),
                    self.gen_copy_method(env),
                    self.gen_dump_method(env),
                    self.gen_update_pids(env),
                    self.gen_normalize_pids(env)]
        return cls

    def copy_marking_expr(self, env, marking_var, *args):
        return ast.Call(func=ast.Attribute(value=ast.Name(id=marking_var.name),
                                           attr='copy'))

    def gen_get_place(self, env, marking_var, place_name, mutable):
        return ast.Attribute(value=ast.Name(id=marking_var.name),
                             attr=self.id_provider.get(place_name))

    ################################################################################
    # Flow elimination
    ################################################################################

    def gen_check_flow(self, env, marking_var, place_info, current_flow):
        place_type = self.get_place_type_by_name(place_info.process_name)
        assert( isinstance(place_type, FlowPlaceType) )
        return place_type.gen_check_flow(env = env,
                                         marking_var = marking_var,
                                         place_name = place_info.name,
                                         current_flow = current_flow)

    def gen_update_flow(self, env, marking_var, place_info):
        place_type = self.get_place_type_by_name(place_info.process_name)
        assert( isinstance(place_type, FlowPlaceType) )
        return place_type.gen_update_flow(env = env,
                                          marking_var = marking_var,
                                          place_info = place_info)

    def gen_read_flow(self, env, marking_var, process_name):
        return self._process_place_types[process_name].gen_read_flow(env, marking_var)

################################################################################

class MarkingSetType(coretypes.MarkingSetType):
    """ Python implementation of the marking set type. """

    def __init__(self, markingtype):
        coretypes.MarkingSetType.__init__(self, markingtype)

    def gen_api(self, env):
        pass

    def new_marking_set_expr(self, env):
        return ast.Call(func=ast.Name(id='set'))

    def add_marking_stmt(self, env, markingset, marking):
        return stmt(ast.Call(func=ast.Attribute(value=ast.Name(id=markingset.name),
                                                attr='add'),
                             args=[E(marking.name)]
                             )
                    )

################################################################################
# opt
################################################################################

class OneSafePlaceType(coretypes.OneSafePlaceType, PythonPlaceType):
    """ Python one safe place Type implementation
    """

    def __init__(self, place_info, marking_type):
        coretypes.OneSafePlaceType.__init__(self,
                                          place_info = place_info,
                                          marking_type = marking_type,
                                          type = TypeInfo.AnyType,
                                          token_type = TypeInfo.AnyType)

    def new_place_expr(self, env):
        return ast.Name(id="None")

    @property
    def token_type(self):
        return self.info.type

    @should_not_be_called
    def iterable_expr(self, env, marking_var): pass

    def remove_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.Assign(targets=[place_expr],
                          value=ast.Name(id='None'))

    def add_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.Assign(targets=[place_expr],
                          value=compiled_token)

    def token_expr(self, env, value):
        return E(repr(value))

    def copy_expr(self, env, marking_var):
        env.add_import('copy')
        place_expr = self.place_expr(env, marking_var)
        return ast.Call(func=ast.Attribute(value=ast.Name(id='copy'),
                                           attr='deepcopy'),
                        args=[place_expr])

    def dump_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.IfExp(test=place_expr,
                         body=ast.BinOp(left = ast.Str('['),
                                        op = ast.Add(),
                                        right = ast.BinOp(left = ast.Call(func=ast.Name('dump'),
                                                                          args=[place_expr]),
                                                          op = ast.Add(),
                                                          right = ast.Str(']')
                                                          )
                                        ),
                         orelse=ast.Str('[]'))

    def enumerate(self, env, marking_var, token_var, compiled_body):
        place_expr = env.marking_type.gen_get_place( env = env,
                                                     marking_var = marking_var,
                                                     place_name = self.info.name,
                                                     mutable = False )
        getnode = ast.Assign(targets=[ast.Name(id=token_var.name)],
                             value=place_expr)
        ifnode = ast.If(test=ast.Compare(left=ast.Name(id=token_var.name),
                                         ops=[ast.NotEq()],
                                         comparators=[ast.Name(id='None')]),
                                         body=[ compiled_body ] )
        return [ getnode, ifnode ]
    
        
################################################################################

class BTPlaceType(coretypes.BTPlaceType, PythonPlaceType):
    """ Python black token place type implementation.

    @attention: Using this place type without the BTTokenEnumerator may introduce inconsistency.
    """

    def __init__(self, place_info, marking_type):
        """
        @param place_info:
        @type place_info: C{}
        @param marking_type:
        @type marking_type: C{}
        """
        coretypes.BTPlaceType.__init__(self,
                                     place_info = place_info,
                                     marking_type = marking_type,
                                     type = TypeInfo.Int,
                                     token_type = TypeInfo.Int)

    def new_place_expr(self, env):
        return ast.Num(n=0)

    def iterable_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.Call(func=ast.Name('xrange'),
                        args=[ast.Num(n=0), place_expr])

    def remove_token_stmt( self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.AugAssign(target=place_expr,
                             op=ast.Sub(),
                             value=ast.Num(1))

    def add_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.AugAssign(target=place_expr,
                             op=ast.Add(),
                             value=ast.Num(1))

    def copy_expr(self, env, marking_var):
        return self.place_expr(env, marking_var)

    def token_expr(self, env, value):
        return E('dot')

    def dump_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.BinOp(left = ast.Str('['),
                         op = ast.Add(),
                         right = ast.BinOp(left = ast.Call(func=E("', '.join"),
                                                           args=[ast.BinOp(left=ast.List([ast.Str('dot')]),
                                                                           op=ast.Mult(),
                                                                           right=place_expr)]),
                                           op = ast.Add(),
                                           right = ast.Str(s=']')
                                           )
                         )
    def enumerate(self, env, marking_var, token_var, compiled_body):
        place_expr = env.marking_type.gen_get_place( env = env,
                                                     marking_var = marking_var,
                                                     place_name = self.info.name,
                                                     mutable = False )
        getnode = ast.Assign(targets=[ast.Name(id=token_var.name)],
                             value=ast.Name(id='dot'))
        ifnode = ast.If(test=ast.Compare(left=place_expr, ops=[ast.Gt()], comparators=[ast.Num(0)]),
                        body=[ getnode, compiled_body ] )
        return [ ifnode ]


################################################################################

class BTOneSafePlaceType(coretypes.BTOneSafePlaceType, PythonPlaceType):
    """ Python one safe black token place type

    Using this place type without the BTOneSafeTokenEnumerator may introduce inconsistency.
    """
    def __init__(self, place_info, marking_type):
        coretypes.BTOneSafePlaceType.__init__(self,
                                            place_info = place_info,
                                            marking_type = marking_type,
                                            type = TypeInfo.Bool,
                                            token_type = TypeInfo.BlackToken)

    def new_place_expr(self, env):
        return E('True')

    @should_not_be_called
    def iterable_expr(self, env, marking_var): pass

    def remove_token_stmt( self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.Assign(targets=[place_expr],
                          value=ast.Name(id='True'))

    def add_token_stmt(self, env, compiled_token, marking_var, *args):
        place_expr = self.place_expr(env, marking_var)
        return ast.Assign(targets=[place_expr],
                          value=ast.Name(id='False'))

    def copy_expr(self, env, marking_var):
        return self.place_expr(env, marking_var)

    def token_expr(self, env, value):
        return E('dot')

    def dump_expr(self, env, marking_var):
        place_expr = self.place_expr(env, marking_var)
        return ast.IfExp(test=ast.UnaryOp(op=ast.Not(), operand=place_expr),
                         body=ast.Str('[ dot ]'),
                         orelse=ast.Str('[]'))

    def enumerate(self, env, marking_var, token_var, compiled_body):
        place_expr = env.marking_type.gen_get_place( env = env,
                                                     marking_var = marking_var,
                                                     place_name = self.info.name,
                                                     mutable = False )
        ifnode = ast.If( test = ast.UnaryOp(op=ast.Not(), operand=place_expr),
                         body = compiled_body )
        return [ ifnode ]
    
################################################################################

class FlowPlaceType(coretypes.PlaceType, PythonPlaceType):
    """ Place type to represent flow control places a specific process.
    """

    def __init__(self, place_info, marking_type):
        """ Build a new place.

        @param place_info:
        @type place_info: C{}
        @param marking_type:
        @type marking_type: C{}
        """
        self._counter = 0
        self._places = {}
        coretypes.PlaceType.__init__(self,
                                     place_info = place_info,
                                     marking_type = marking_type,
                                     type = TypeInfo.Int,
                                     token_type = TypeInfo.Int)

    @property
    def is_ProcessPlace(self):
        return True

    @property
    def token_type(self):
        """ Get python type of the stored token
        """
        return TypeInfo.Int

    def new_place_expr(self, env):
        """ Produce a new empty place.

        @returns: empty place expression
        @rtype: C{Expr}
        """
        return E("0")

    @should_not_be_called
    def iterable_expr(self, env, marking_var): pass

    @should_not_be_called
    def remove_token_stmt( self, *args, **kwargs): pass

    @should_not_be_called
    def add_token_stmt(self, *args, **kwargs): pass

    def copy_expr(self, env, marking_var):
        """ produce an expression corresponding to a copy of the place.

        @param env: compiling environment
        @type env: C{Env}
        @param marking_var: marking storing the place
        @type marking_var: C{VariableInfo}
        """
        return self.place_expr(env, marking_var)

    def add_place(self, place_info):
        """ Adds a flow control place.

        @param place_info: flow control place to be added
        @type place_info: C{PlaceInfo}
        """
        assert(place_info.flow_control)
        assert(not self._places.has_key(place_info.name))
        self._places[place_info.name] = self._counter
        self._counter += 1

    def gen_check_flow(self, env, marking_var, place_name, current_flow):
        """ Get an ast representing the flow check.
        """
        return ast.Compare(left=current_flow,
                           ops=[ast.Eq()],
                           comparators=[ast.Num(self._places[place_name])])

    def gen_update_flow(self, env, marking_var, place_info):
        """ Get an ast representing the flow update.
        """
        place_expr = self.place_expr(env, marking_var)
        return ast.Assign(targets=[place_expr],
                          value=ast.Num(self._places[place_info.name]))

    def gen_read_flow(self, env, marking_var):
        return self.place_expr(env, marking_var)

    def dump_expr(self, env, marking_var, variable):
        place_expr =  self.place_expr(env, marking_var)
        l = []
        for place in self._places:
            l.append( stmt(ast.Call(func=E('{}.append'.format(variable.name)),
                                    args=[ ast.BinOp(left=ast.Str( repr(place) + ' : '),
                                                     op=ast.Add(),
                                                     right=ast.IfExp(test=self.gen_check_flow(env, marking_var, place, place_expr),
                                                                     body=ast.Str('[ dot ],'),
                                                                     orelse=ast.Str('[],'))
                                                     ) ]
                                    )
                           )
                      )
        return l

################################################################################
# EOF
################################################################################
