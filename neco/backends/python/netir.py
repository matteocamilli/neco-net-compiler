""" Python ast compiler. """

import ast
import cPickle as cPickle
import StringIO
import neco.config as config
import neco.core.netir as coreir
from neco.core.info import *
from astutils import Builder, E, A, stmt, to_ast
from nettypes import type2str

################################################################################

class CompilerVisitor(coreir.CompilerVisitor):
    """ Python ast compiler visitor class. """

    backend = "python"

    def __init__(self, env):
        self.env = env

    def compile_Print(self, node):
        return ast.Print(dest = None,
                         values = [ ast.Str( s = node.message ) ],
                         nl = True)

    def compile(self, node):
        return to_ast(super(CompilerVisitor, self).compile(node))

    def compile_Comment(self, node):
        return []

    def compile_If(self, node):
        return Builder.If( test = self.compile(node.condition),
                           body = [ self.compile(node.body) ],
                           orelse = [ self.compile(node.orelse) ] )

    def compile_Compare(self, node):
        return Builder.Compare( left = self.compile(node.left),
                                ops = [ self.compile(op) for op in node.ops ],
                                comparators = [ self.compile(comparator) for comparator in node.comparators ] )

    def compile_EQ(self, node):
        return Builder.Eq()

    def compile_CheckTuple(self, node):
        tuple_info = node.tuple_info
        test = E( "isinstance(" + node.tuple_name +  ", tuple) and len(" + node.tuple_name + ") == " + repr(len(tuple_info)) )
        return Builder.If( test = test, body = self.compile(node.body) )

    def compile_CheckType(self, node):
        type_info = node.type
        if type_info.is_AnyType:
            return self.compile(node.body)

        test = E("isinstance(" + node.variable.name + ", " + type2str(node.type) + ")")
        return Builder.If( test = test, body = self.compile(node.body) )

    def compile_Match(self, node):
        tuple_info = node.tuple_info
        seq = []
        seq.append( E(Builder.Tuple([ E(name) for name in tuple_info.base() ])).assign(E(tuple_info.name)) )
        cur = None
        for component in tuple_info.components:
            if component.is_Value:
                n = Builder.If( test = E(component.name).Eq(E(repr(component.raw))) )
                if cur == None:
                    cur = n
                    seq.append(n)
                else:
                    cur.body = [n]
                    cur = n

        if cur != None:
            cur.body = [ self.compile( node.body ) ]
        else:
            seq.append(self.compile( node.body ))

        return seq


    def compile_Assign(self, node):
        return E(node.variable.name).assign(self.compile(node.expr))

    def compile_Value(self, node):
        place_type = self.env.marking_type.get_place_type_by_name(node.place_name)
        return place_type.gen_build_token(self.env, node.value.raw)

    def compile_Pickle(self, node):
        output = StringIO.StringIO()
        cPickle.dump(node.obj, output)
        pickle_str = output.getvalue()
        return E("cPickle.load(StringIO.StringIO(" + repr(pickle_str) + "))")

    def compile_FlushIn(self, node):
        destination_place = self.env.marking_type.get_place_type_by_name(node.place_name)
        place_expr = destination_place.place_expr(self.env, node.marking_name)
        return [ E(node.token_name).assign(place_expr),
                 destination_place.gen_clear_function_call(self.env, node.marking_name) ]

    def compile_FlushOut(self, node):
        destination_place = self.env.marking_type.get_place_type_by_name(node.place_name)
        multiset = self.compile(node.token_expr)
        return destination_place.add_items( env = self.env,
                                            multiset = multiset,
                                            marking_name = node.marking_name )

    def gen_tuple(self, tuple_info):
        elts = []
        for info in tuple_info:
            if info.is_Value:
                elts.append( E(repr(info.raw)) )

            elif info.is_Variable:
                elts.append( E(info.name) )

            elif info.is_Tuple:
                elts.append( self.gen_tuple( info ) )
            elif info.is_Expression:
                elts.append( E(info.raw) )
            else:
                raise NotImplementedError, info.component.__class__

        return Builder.Tuple(elts)

    def compile_TupleOut(self, node):
        tuple_info = node.tuple_info
        tuple = self.gen_tuple(tuple_info)
        return self.env.marking_type.gen_add_token_function_call(env = self.env,
                                                                 token = tuple,
                                                                 marking_name = node.marking_name,
                                                                 place_name = node.place_name)

    def compile_NotEmpty(self, node):
        return self.env.marking_type.gen_not_empty_function_call( env = self.env,
                                                                  marking_name = node.marking_name,
                                                                  place_name = node.place_name )

    def compile_TokenEnumeration(self, node):
        return Builder.For( target = E(node.token_name),
                            iter = self.env.marking_type.gen_iterable_place( env = self.env,
                                                                             marking_name = node.marking_name,
                                                                             place_name = node.place_name),
                            body = [ self.compile(node.body) ] )

    def compile_MultiTokenEnumeration(self, node):
        """

        produce:

        ...
        i = 0 # init offset
        for x in s1:
          i += 1
          j = 0
          for y in s2:
            j += 1
            if i != j: # check offsets
              ...

        """
        base, current = None, None
        place_type = self.env.marking_type.get_place_type_by_name(node.place_name)

        for name, offset in zip(node.token_names, node.offset_names):
            # gen: i = 0
            pred = E(offset).assign(E('0'))
            # gen: for x in s1
            child = Builder.For( target = E(name),
                                 iter = self.env.marking_type.gen_iterable_place( env = self.env,
                                                                                  marking_name = node.marking_name,
                                                                                  place_name = node.place_name) )
            # gen: i += 1
            child.body.append( E(offset).add_assign(E('1')) )
            # initial block
            if not base:
                base = [pred, child]

            # update current
            if current:
                current.body.extend( [ pred, child ] )
            current = child

        # check offsets
        def gen_different(offs, most_inner):
            if len(offs) == 1:
                return most_inner
            offset = offs.pop()
            current = None
            base = None
            for offset2 in offs:
                n = Builder.If( test = E(offset).NotEq(E(offset2)) )
                if not base:
                    base = n
                if current:
                    current.body.extend( n )
                current = n
            current.body.extend( gen_different(offs, most_inner) )
            return base

        current.body.extend( [ gen_different( node.offset_names, most_inner = [ self.compile(node.body) ] ) ] )
        return base

    def compile_GuardCheck(self, node):
        return Builder.If( test = self.compile(node.condition),
                           body = self.compile(node.body) )

    def compile_PyExpr(self, node):
        assert isinstance(node.expr, ExpressionInfo)
        return E(node.expr.raw)

    def compile_Name(self, node):
        return E(node.name)

    def compile_FunctionCall(self, node):
        return E(node.function_name).call([ self.compile(arg) for arg in node.arguments ])

    def compile_ProcedureCall(self, node):
        return stmt( E(node.function_name).call([ self.compile(arg) for arg in node.arguments ]) )

    def compile_MarkingCopy(self, node):
        nodes = []
        nodes.append( E( node.dst_name + " = Marking()" ) )

        names = {}
        for info in node.mod:
            names[info.name] = info

        for (place, place_type) in self.env.marking_type.place_types.iteritems():
            dst_place_expr = place_type.place_expr(self.env, marking_name = node.dst_name)
            src_place_expr = place_type.place_expr(self.env, marking_name = node.src_name)
            if names.has_key( place ):
                nodes.append( E(dst_place_expr).assign(place_type.gen_copy(self.env, node.src_name)) )
            else:
                nodes.append( E(dst_place_expr).assign(src_place_expr) )
        return nodes

    def compile_AddMarking(self, node):
        return self.env.marking_set_type.gen_add_marking_function_call(env = self.env,
                                                                       markingset_name = node.markingset_name,
                                                                       marking_name = node.marking_name)

    def compile_AddToken(self, node):
        return self.env.marking_type.gen_add_token_function_call(env = self.env,
                                                                 token = self.compile(node.token_expr),
                                                                 marking_name = node.marking_name,
                                                                 place_name = node.place_name)

    def compile_RemToken(self, node):
        return self.env.marking_type.gen_remove_token_function_call(env = self.env,
                                                                    token = self.compile(node.token_expr),
                                                                    marking_name = node.marking_name,
                                                                    place_name = node.place_name)

    def compile_RemTuple(self, node):
        return self.env.marking_type.gen_remove_token_function_call(env = self.env,
                                                                    token = self.compile(node.tuple_expr),
                                                                    marking_name = node.marking_name,
                                                                    place_name = node.place_name)

    def compile_Token(self, node):
        return self.env.marking_type.gen_build_token(env = self.env,
                                                     place_name = node.place_name,
                                                     value = node.value)

    def compile_SuccT(self, node):
        stmts = [ self.compile( node.body ),
                  E('return ' + node.markingset_name) ]
        return Builder.FunctionDef(name = node.function_name,
                                   args = A(node.markingset_name).param(node.marking_name),
                                   body = stmts)

    def compile_SuccP(self, node):
        stmts = [ self.compile( node.body ),
                  E('return ' + node.markingset_name) ]
        return Builder.FunctionDef(name = node.function_name,
                                   args = A(node.markingset_name).param(node.marking_name),
                                   body = stmts)

    def compile_Succs(self, node):
        body = [ E(node.markingset_variable_name).assign(self.env.marking_set_type.gen_new_marking_set(self.env)) ]

        body.extend( self.compile( node.body ) )
        body.append( E("return " + node.markingset_variable_name) )
        return Builder.FunctionDef( name = node.function_name,
                                    args = A(node.marking_argument_name),
                                    body = body )

    def compile_Init(self, node):
        new_marking = E(node.marking_name).assign(self.env.marking_type.gen_alloc_marking_function_call(self.env))
        return_stmt = E('return ' + node.marking_name)

        stmts = [new_marking]
        stmts.extend( self.compile(node.body) )
        stmts.append( return_stmt )

        return Builder.FunctionDef( name = node.function_name,
                                    body = stmts )

    ################################################################################
    # opts
    ################################################################################
    def compile_OneSafeTokenEnumeration(self, node):
        place_expr = self.env.marking_type.gen_get_place( env = self.env,
                                                          marking_name = node.marking_name,
                                                          place_name = node.place_name,
                                                          mutable = False )
        getnode = E(node.token_name).assign(place_expr)
        ifnode = Builder.If( test = E(node.token_name).NotEq(E('None')),
                             body = [ self.compile( node.body ) ] )
        return [ getnode, ifnode ]

    def compile_BTTokenEnumeration(self, node):
        place_expr = self.env.marking_type.gen_get_place( env = self.env,
                                                          marking_name = node.marking_name,
                                                          place_name = node.place_name,
                                                          mutable = False )
        getnode = E(node.token_name).assign(E('dot'))
        ifnode = Builder.If( test = E(place_expr).Gt(E('0')),
                             body = [ getnode, self.compile( node.body ) ] )
        return [ ifnode ]

    def compile_BTOneSafeTokenEnumeration(self, node):
        getnode = E(node.token_name).assign('dot')
        if node.token_is_used:
            body = [ getnode, self.compile( node.body ) ]
        else:
            body = [ self.compile( node.body ) ]

        place_expr = self.env.marking_type.gen_get_place( env = self.env,
                                                          marking_name = node.marking_name,
                                                          place_name = node.place_name,
                                                          mutable = False )
        ifnode = Builder.If( test = Builder.Not(E(place_expr)),
                             body = body )
        return [ ifnode ]

    ################################################################################
    # Flow elimination
    ################################################################################

    def compile_FlowCheck(self, node):
        return self.env.marking_type.gen_check_flow(env = self.env,
                                                    marking_name = node.marking_name,
                                                    place_info = node.place_info,
                                                    current_flow = E(current_flow.name))

    def compile_ReadFlow(self, node):
        return self.env.marking_type.gen_read_flow(env=self.env,
                                                   marking_name=node.marking_name,
                                                   process_name=node.process_name)

    def compile_UpdateFlow(self, node):
        return self.env.marking_type.gen_update_flow(env = self.env,
                                                     marking_name = node.marking_name,
                                                     place_info = node.place_info)

################################################################################
# EOF
################################################################################
