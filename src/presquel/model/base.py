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
        self._order = (int(order[0]), int(order[1]), int(order[2]))

    def items(self):
        return self._order

    def __str__(self):
        return repr(self._order)

    def __repr__(self):
        return 'Order(' + repr(self._order) + ')'

    def __sub__(self, other):
        assert isinstance(other, Order)
        assert len(self._order) == len(other._order)
        for i in range(0, len(self._order)):
            x = self._order[i] - other._order[i]
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


class SqlArgument(object):
    """
    An argument passed to the SQL code.
    """
    def __init__(self, name, basic_type, is_collection = False):
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

    def get_for_platform(self, platforms):
        """
        Returns the most appropriate SqlString instance, starting with the
        first platform value.

        :param platforms: tuple(str) or str
        :return: SqlString if match, or None if no match.
        """
        if isinstance(platforms, str):
            platforms = [ platforms ]

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
                       VIEW_TYPE)
