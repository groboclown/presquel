"""
Base objects used in the model.

The model is intended to be read-only.
"""


class Order(object):
    def __init__(self, order):
        object.__init__(self)
        if not isinstance(order, list) and not isinstance(order, tuple):
            raise Exception("order must be list(int), but found " + repr(order))
        if not len(order) == 3:
            raise Exception("order must be of length 3, but found " +
                            repr(order))
        self.__order = (int(order[0]), int(order[1]), int(order[2]))

    def items(self):
        return self.__order

    def __str__(self):
        return repr(self.__order)

    def __repr__(self):
        return 'Order(' + repr(self.__order) + ')'

    def __sub__(self, other):
        assert isinstance(other, Order)
        assert len(self.__order) == len(other.__order)
        for i in range(0, len(self.__order)):
            x = self.__order[i] - other.__order[i]
            if x != 0:
                return x
        return 0

    def __lt__(self, other):
        assert isinstance(other, Order)
        return self - other < 0

    def __le__(self, other):
        assert isinstance(other, Order)
        return self - other <= 0

    def __gt__(self, other):
        assert isinstance(other, Order)
        return self - other > 0

    def __ge__(self, other):
        assert isinstance(other, Order)
        return self - other >= 0


class BaseObject(object):
    """
    Base schema object, used by changes and schema definitions for user
    constructed schema.
    """
    def __init__(self, order, comment, object_type):
        object.__init__(self)
        if isinstance(order, list) or isinstance(order, tuple):
            order = Order(order)
        if not isinstance(order, Order):
            raise Exception("order must be Order, found " + repr(order))
        if comment is not None and not isinstance(comment, str):
            raise Exception("comment must be str, but found " + repr(comment))
        assert isinstance(object_type, SchemaObjectType)
        self.__order = order
        self.__comment = comment
        self.__object_type = object_type

    @property
    def order(self):
        return self.__order

    @property
    def comment(self):
        return self.__comment

    @property
    def object_type(self):
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


class SqlSet(object):
    def __init__(self, sql_set):
        assert ((isinstance(sql_set, tuple) or isinstance(sql_set, list))
                and len(sql_set) > 0)
        self.__sql_set = sql_set

    def get(self):
        ret = []
        ret.extend(self.__sql_set)
        return ret

    def get_for_platform(self, platforms):
        """
        Returns the most appropriate SqlString instance, starting with the
        first platform value.

        :param platforms: tuple(str) or str
        :return: SqlString if match, or None if no match.
        """
        if isinstance(platforms, str):
            platforms = [platforms]

        for p in platforms:
            p = p.strip().lower()
            for sql in self.__sql_set:
                assert isinstance(sql, SqlString)
                for sp in sql.platforms:
                    if p == sp:
                        return sql
        for sql in self.__sql_set:
            assert isinstance(sql, SqlString)
            if (sql.syntax == 'universal' or 'any' in sql.platforms or
                    'all' in sql.platforms):
                return sql
        return None

    def sql_args(self, platforms, arg_converter):
        """
        Return the sql for the given platforms, with the argument values
        replaced, using the function "arg_converter", which takes the argument
        name as input, and outputs the prepared statement replacement string.

        :param arg_converter:
        :return:
        """
        ret = self.get_for_platform(platforms)
        if ret is None:
            return None
        ret = ret.sql
        for a in self.arguments:
            ret = ret.replace('{' + a + '}', arg_converter(a))
        return ret


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
                       VIEW_TYPE)
