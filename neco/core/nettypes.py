""" Module providing type structures.
"""

import types
from abc import abstractmethod, ABCMeta
import snakes.nets as nets
from neco import utils, config
from info import TypeInfo

################################################################################

def provides_by_index_access(cls):
    cls._by_index_access_ = True
    return cls

def provides_by_index_deletion(cls):
    cls._by_index_deletion_ = True
    return cls

class PlaceType(object):
    """ Common base class for place types.
    """

    __metaclass__ = ABCMeta

    _by_index_access_   = False
    _by_index_deletion_ = False

    def __init__(self, place_info, marking_type, type, token_type):
        """ Initialise the place type.
        """
        self.info = place_info
        self.marking_type = marking_type
        self._type = type
        self._token_type = token_type

    @property
    def type(self):
        return self._type

    @property
    def token_type(self):
        return self._token_type

    @property
    def process_name(self):
        return self.info.process_name

    @property
    def provides_by_index_access(self):
        return self.__class__._by_index_access_

    @property
    def provides_by_index_deletion(self):
        return self.__class__._by_index_deletion_

################################################################################

class ObjectPlaceType(PlaceType):
    """ Fallback place type.
    """

    def __init__(self, place_info, marking_type, type, token_type):
        PlaceType.__init__(self,
                           place_info = place_info,
                           marking_type = marking_type,
                           type = type,
                           token_type = token_type)

################################################################################

class MarkingType(object):
    """ Common base class for all marking types.
    """
    __metaclass__ = ABCMeta

    def __init__(self, type_name):
        """ Create a new marking type providing a type name.

        @param type_name: marking structure type name.
        @type type_name: C{str}
        """
        self.type_name = type_name
        self.place_types = dict()

        self._places = set()
        self._flow_control_places = set()
        self._one_safe_places = set()

        self._use_control_flow_elimination = config.get('process_flow_elimination')

    @property
    def use_control_flow_elimination(self):
        return self._use_control_flow_elimination

    @property
    def type(self):
        return TypeInfo.register_type(self.type_name)

    @property
    def places(self):
        return self._places

    @property
    def flow_control_places(self):
        return self._flow_control_places

    @property
    def one_safe_places(self):
        return self._one_safe_places

    def get_place_type_by_name(self, name):
        """ Retrieve a place by name.

        @param name: place name.
        @type name: C{str}
        @return: place type.
        @rtype: C{PlaceType}
        """
        return self.place_types[name]

    def append(self, place_info):
        """ Add a place info instance to marking type.

        The place info will be added into a list depending on its properties.
        A flow control place will be added to C{self.flow_control_places},
        a one bounded place will be added to C{self.one_safe_places}, other
        places will be addeed to C{self.places}.

        @param place_name: place name
        @type place_name: C{str}
        """
        if self.use_control_flow_elimination and place_info.flow_control:
            self._flow_control_places.add( place_info )
        elif place_info.one_safe:
            self._one_safe_places.add( place_info )
        else:
            self._places.add( place_info )


    @abstractmethod
    def gen_types(self, select_type):
        """ Create place types from place info datas.
        """
        pass

    @abstractmethod
    def gen_api(self, *args):
        """ Produce all the structures and functions needed to manage the marking.

        @return: marking structure ast (backend specific).
        @rtype: C{ast} (backend specific).
        """
        pass

    @abstractmethod
    def new_marking_expr(self, marking_name, *args):
        """ Build an expression producing a new marking.
        """
        pass

    @abstractmethod
    def free_marking_stmt(self, marking_name, *args):
        """ Produce a \"free\" stmt for deleting a marking.
        """
        pass

    @abstractmethod
    def copy_marking_expr(self, marking_name, *args):
        """ Produce a copy expression for the marking.

        @return: function call
        @rtype: implementation specific, see backends
        """
        pass

    # @abstractmethod
    # def remove_token_stmt(self, token_name, marking_name, place_name, *args):
    #     """ Produce a remove token statement for the representation.
    #     """
    #     pass

    # @abstractmethod
    # def add_token_stmt(self, token_name, marking_name, place_name, *args):
    #     """ Produce a add token statement for the representation.
    #     """
    #     pass


################################################################################

class MarkingSetType(object):
    """ Common base class for marking set types.
    """

    __metaclass__ = ABCMeta

    def __init__(self, marking_type):
        """ Initialise marking set structure

        @param marking_type: marking set type.
        @type marking_type: C{str}
        """
        self.marking_type = marking_type

    @abstractmethod
    def gen_api(self):
        """ Produce all functions provided by the marking set structure.
        """
        pass

    @abstractmethod
    def add_marking_stmt(self, marking_set_name, marking_name):
        """ Produce a add marking function call for the marking set structure.
        """
        pass

################################################################################
# EOF
################################################################################

