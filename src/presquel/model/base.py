"""
Base objects used in the model.

The model is intended to be read-only.
"""

import functools

class Order(object):
    def __init__(self, order: list or tuple,
                 before: None or tuple or list,
                 after: None or tuple or list):
        object.__init__(self)
        if not isinstance(order, list) and not isinstance(order, tuple):
            raise Exception("order must be list(int), but found " + repr(order))
        if not len(order) == 3:
            raise Exception("order must be of length 3, but found " +
                            repr(order))
        self._order = (int(order[0]), int(order[1]), int(order[2]))
        self.__before = Order._clean_order_list(before)
        self.__after = Order._clean_order_list(after)

    def items(self):
        return self._order

    @property
    def occurs_before(self) -> tuple:
        """
        All the abstract concepts that this order must happen before.
        That is, all these items will be sorted after this object.

        :rtype: tuple[str]
        """
        return self.__before

    @property
    def occurs_after(self):
        """
        All the abstract concepts that this order must happen after.  This means
        the order will be sorted such that these concepts are before this order.

        :rtype: tuple[str]
        """
        return self.__after

    def __str__(self):
        return repr(self._order)

    def __repr__(self):
        return ('Order(' + repr(self._order) + ', ' + repr(self.__before) +
                ', ' + repr(self.__after) + ')')

    def __sub__(self, other):
        assert isinstance(other, Order)
        assert len(self._order) == len(other._order)
        for i in range(0, len(self._order)):
            x = self._order[i] - other._order[i]
            if x != 0:
                return x
        return 0

    def __lt__(self, other):
        """Natural ordering, without looking at the before/after loops."""
        assert isinstance(other, Order)
        return self - other < 0

    def __le__(self, other):
        """Natural ordering, without looking at the before/after loops."""
        assert isinstance(other, Order)
        return self - other <= 0

    def __gt__(self, other):
        """Natural ordering, without looking at the before/after loops."""
        assert isinstance(other, Order)
        return self - other > 0

    def __ge__(self, other):
        """Natural ordering, without looking at the before/after loops."""
        assert isinstance(other, Order)
        return self - other >= 0

    @staticmethod
    def _clean_order_list(order: list or tuple or None) -> tuple:
        """

        :param order:
        :type order: list[str] or tuple[str] or None
        :rtype: tuple[str]
        """
        if order is None:
            return tuple()
        ret = []
        for val in order:
            assert isinstance(val, str)
            cleaned = Order._clean_order_str(val)
            if cleaned is not None:
                ret.append(cleaned)
        return tuple(ret)

    @staticmethod
    def _clean_order_str(order_str: str) -> None or str:
        """Strip out all non-alpha numeric characters except '.'."""
        ret = ""
        for val in order_str:
            if val.isalnum() or val == '.':
                ret += val
        if len(ret) <= 0:
            return None
        return ret

    @staticmethod
    def full_sort(orders: list or tuple) -> list:
        """
        Full sorting of the order list.  Uses the natural ordering of the
        orders, with the additional constraints of the before/after ordering.

        :type orders: list[Order] or tuple[Order]
        :rtype: list[Order]
        """

        # We set up the topo sort to include the "before" and "after" objects
        # as another element in the sort.  These are injected into the to-be
        # sorted list, and removed at the end.

        # Setup the topo sort.
        input_list = list(orders)

        def input_sorter(a, b) -> int:
            if isinstance(a, str):
                if isinstance(b, str):
                    return (a == b and 0) or (a < b and -1) or 1
                else:
                    # Orders always come before strings
                    return 1
            elif isinstance(b, str):
                return -1
            else:
                assert isinstance(a, Order)
                assert isinstance(b, Order)
                return a - b

        is_visiting = {}
        visiting_stack = []

        depends = {}

        # Translate before / after into a strict dependency.
        for order in orders:
            assert isinstance(order, Order)
            depends[order] = list(order.occurs_after)
            # We don't need to capture the after in our dependency list -
            # if everything marks itself as being after something, but nothing
            # is before it, then it isn't necessary for the ordering.
            for name in order.occurs_before:
                if name in depends:
                    depends[name].append(order)
                else:
                    depends[name] = [order]
                    input_list.append(name)

        # Sort the "natural" order (non-dependency check)
        input_list.sort(key=functools.cmp_to_key(input_sorter))
        for dep_list in depends.values():
            dep_list.sort(key=functools.cmp_to_key(input_sorter))

        # For each order item, run a Depth First Search-based sort
        # By putting the orders in a numbered sort first, we urge the
        # search to maintain the correct order.

        sorted_list = []
        for val in input_list:
            if val not in is_visiting:
                Order.__tsort(val, depends, is_visiting,
                              visiting_stack, sorted_list)
            elif is_visiting[val]:
                # FIXME make this a warning?  Definitely need better debugging.
                raise Exception("cyclic dependency in orders (FIXME add better debugging)")

        ret = []
        for val in sorted_list:
            if isinstance(val, Order):
                ret.append(val)
        return ret

    @staticmethod
    def __tsort(input_val, depends: dict, is_visiting: dict,
                visiting_stack: list, ret: list):
        """
        Perform a single step in a highly modified depth-first-search.

        :type input_val: Order or str
        :type depends: dict[Order or str, list[Order or str]]
        :type is_visiting: dict[Order, bool]
        :type visiting_stack: list[Order or str]
        :type ret: list[Order or str]
        """

        is_visiting[input_val] = True
        visiting_stack.append(input_val)

        if input_val in depends:
            for dep in depends[input_val]:
                if dep not in is_visiting:
                    # Has not been visited yet
                    Order.__tsort(dep, depends, is_visiting,
                                  visiting_stack, ret)
                elif is_visiting[dep]:
                    # Circular dependency
                    # FIXME make this a warning?  Definitely need better debugging.
                    raise Exception(
                        "cyclic dependency in orders (FIXME add better debugging)")
        recent = visiting_stack.pop()
        if recent != input_val:
            raise Exception("Unexpected internal error (bad sort algorithm)")
        is_visiting[input_val] = False
        ret.append(input_val)


class SchemaObjectType(object):
    """
    Describes the kind of schema object.  Should be considered an enum.
    """

    def __init__(self, name):
        object.__init__(self)
        self.__name = name

    @property
    def name(self):
        return self.__name


class BaseObject(object):
    """
    Base schema object, used by changes and schema definitions for user
    constructed schema.
    """
    def __init__(self, order: Order, comment, object_type):
        object.__init__(self)
        if not isinstance(order, Order):
            raise Exception("order must be Order, found " + repr(order))
        if comment is not None and not isinstance(comment, str):
            raise Exception("comment must be str, but found " + repr(comment))
        assert isinstance(object_type, SchemaObjectType)
        self.__order = order
        self.__comment = comment
        self.__object_type = object_type

    @property
    def order(self) -> Order:
        return self.__order

    @property
    def comment(self) -> str:
        return self.__comment

    @property
    def object_type(self) -> SchemaObjectType:
        return self.__object_type

    def __lt__(self, change):
        assert isinstance(change, BaseObject)
        return self.order < change.order

    def __le__(self, change):
        assert isinstance(change, BaseObject)
        return self.order <= change.order

    def __gt__(self, change):
        assert isinstance(change, BaseObject)
        return self.order > change.order

    def __ge__(self, change):
        assert isinstance(change, BaseObject)
        return self.order >= change.order

    @staticmethod
    def full_sort(objects: list or tuple) -> list:
        """
        Fully sorts the list of BaseObject using the order.

        :type objects: list[BaseObject] or tuple[BaseObject]
        :rtype: list[BaseObject]
        """

        # This is inefficient.  It should instead use a key
        # in the order sort, but that would be even more complications to that
        # already complex algorithm.

        object_order_map = {}
        orders = []
        for obj in objects:
            assert obj.order not in object_order_map
            object_order_map[obj.order] = obj
            orders.append(obj.order)

        orders = Order.full_sort(orders)
        ret = []
        for order in orders:
            ret.append(object_order_map[order])
        return ret


class SqlString(object):
    def __init__(self, sql, syntax, platforms):
        object.__init__(self)
        assert isinstance(sql, str) and len(sql) > 0
        assert isinstance(syntax, str) and len(syntax) > 0
        assert ((isinstance(platforms, tuple) or isinstance(platforms, list))
                and len(platforms) > 0)
        self.__sql = sql
        self.__syntax = syntax.strip().lower()
        self.__platforms = [p.strip().lower() for p in platforms]

    # TODO allow for priorities on the platform

    @property
    def sql(self):
        return self.__sql

    @property
    def syntax(self):
        return self.__syntax

    @property
    def platforms(self):
        return self.__platforms


class SqlArgument(object):
    """
    An argument passed to the SQL code.
    """
    def __init__(self, name, basic_type, is_collection: bool=False):
        object.__init__(self)
        self.__name = name
        self.__basic_type = basic_type
        self.__is_collection = is_collection

    @property
    def name(self):
        return self.__name

    @property
    def basic_type(self):
        return self.__basic_type

    @property
    def is_collection(self):
        return self.__is_collection


class SqlSet(object):
    """
    A collection of the SQL snippets for the different platforms, along with
    the parameterized arguments.
    """
    def __init__(self, sql_set, arguments):
        assert ((isinstance(sql_set, tuple) or isinstance(sql_set, list))
                and len(sql_set) > 0)
        if arguments is None:
            arguments = []
        assert (isinstance(arguments, list) or isinstance(arguments, tuple))
        for a in arguments:
            assert isinstance(a, SqlArgument)
        self.__sql_set = sql_set
        self.__arguments = tuple(arguments)

    def get(self):
        return tuple(self.__sql_set)

    def get_for_platform(
            self, platforms: str or list or tuple) -> None or SqlString:
        """
        Returns the most appropriate SqlString instance, starting with the
        first platform value.

        :param platforms: tuple[str] or list[str] or str
        :return: SqlString if match, or None if no match.
        """
        if isinstance(platforms, str):
            platforms = [platforms]

        for plat in platforms:
            plat = plat.strip().lower()
            for sql in self.__sql_set:
                assert isinstance(sql, SqlString)
                for spl in sql.platforms:
                    if plat == spl:
                        return sql
        for sql in self.__sql_set:
            assert isinstance(sql, SqlString)
            if (sql.syntax == 'universal' or 'any' in sql.platforms or
                    'all' in sql.platforms):
                return sql
        return None

    @property
    def arguments(self):
        return self.__arguments

    @property
    def collection_arguments(self):
        ret = []
        for arg in self.arguments:
            if arg.is_collection:
                ret.append(arg)
        return ret

    @property
    def simple_arguments(self):
        ret = []
        for arg in self.arguments:
            if not arg.is_collection:
                ret.append(arg)
        return ret


class LanguageArgument(object):
    """
    """
    def __init__(self, name, generic_type):
        assert isinstance(name, str)
        assert isinstance(generic_type, str)

        object.__init__(self)

        self.__name = name
        self.__generic_type = generic_type

    @property
    def name(self):
        return self.__name

    @property
    def generic_type(self):
        return self.__generic_type


class LanguageSet(object):
    """
    A collection of the different languages supported for code generation,
    and the arguments they require.
    """
    def __init__(self, language_dict, arguments):
        """
        :param language_dict: map between language name and the code.
        :param arguments: list of strings with the argument names the code uses.
        """
        assert isinstance(language_dict, dict) and len(language_dict) > 0
        langs = {}
        for name, code in language_dict.items():
            assert isinstance(name, str)
            assert isinstance(code, str)
            name = name.strip().lower()
            assert name not in langs
            langs[name] = code

        if arguments is None:
            arguments = []
        assert isinstance(arguments, list) or isinstance(arguments, tuple)
        for arg in arguments:
            assert isinstance(arg, LanguageArgument)
        self.__languages = langs
        self.__arguments = tuple(arguments)

    def get_for_language(self, language):
        """
        Returns the most appropriate code.  The code should have a SQL value
        (or some other variable) that it sends its code to.

        :param language: str
        :return: string if match, or None if no match.
        """
        assert isinstance(language, str)

        language = language.strip().lower()
        if language in self.__languages:
            code = self.__languages[language]
            return code
        return None

    @property
    def arguments(self):
        """
        :return a tuple of LanguageArgument
        """
        return self.__arguments


COLUMN_TYPE = SchemaObjectType('column')
CONSTRAINT_TYPE = SchemaObjectType('constraint')
LOOKUP_TABLE_TYPE = SchemaObjectType('lookup table')
PRIMARY_KEY_TYPE = SchemaObjectType('primary key')
SEQUENCE_TYPE = SchemaObjectType('sequence')
INDEX_TYPE = SchemaObjectType('index')
TABLE_TYPE = SchemaObjectType('table')
VIEW_TYPE = SchemaObjectType('view')
DATA_TYPE = SchemaObjectType('data')
PROCEDURE_TYPE = SchemaObjectType('procedure')
SCHEMA_OBJECT_TYPES = (COLUMN_TYPE, CONSTRAINT_TYPE, LOOKUP_TABLE_TYPE,
                       PRIMARY_KEY_TYPE, SEQUENCE_TYPE, INDEX_TYPE, TABLE_TYPE,
                       VIEW_TYPE, DATA_TYPE, PROCEDURE_TYPE)

