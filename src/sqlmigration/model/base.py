"""
Base objects used in the model.

The model is intended to be read-only.
"""



class BaseObject(object):
    """
    Base schema object, used by changes and schema definitions for user
    constructed schema.
    """
    def __init__(self, order, comment, object_type):
        object.__init__(self)
        if not isinstance(order, int):
            raise Exception("order must be int, but found " + repr(order))
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
        return (self.order - change.order) < 0

    def __le__(self, change):
        assert isinstance(change, BaseObject)
        return (self.order - change.order) <= 0

    def __gt__(self, change):
        assert isinstance(change, BaseObject)
        return (self.order - change.order) > 0

    def __ge__(self, change):
        assert isinstance(change, BaseObject)
        return (self.order - change.order) >= 0


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
