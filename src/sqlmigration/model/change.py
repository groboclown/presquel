"""
Classes that encompass changes to the schema.  Changes are associated with
a version's schema.  All the changes should migrate the database from the
previous version to the current version.
"""

from .base import BaseObject


class ChangeType(object):
    """
    Describes the type of change performed.  Should be considered an enum.
    """
    def __init__(self, name):
        object.__init__(self)
        self.__name = name

    @property
    def name(self):
        return self.__name


ADD_CHANGE = ChangeType('add')
REMOVE_CHANGE = ChangeType('remove')
RENAME_CHANGE = ChangeType('rename')
ALTER_CHANGE = ChangeType('alter')
SQL_CHANGE = ChangeType('sql')
CHANGE_TYPES = (ADD_CHANGE, REMOVE_CHANGE, RENAME_CHANGE, ALTER_CHANGE, SQL_CHANGE)


class Change(BaseObject):
    """
    A single change to a schema object.  It can either be top-level
    (i.e. drop a table) or within a schema object (i.e. rename a table).

    These do not need to be specified for the creation of an object.

    The base change class can be used if the change is trivial (see docs).
    Non-trivial changes require a sql change.
    """
    def __init__(self, order, comment, object_type, change_type):
        BaseObject.__init__(self, order, comment, object_type)
        assert isinstance(change_type, ChangeType)
        self.__change_type = change_type
        self.parent = None

    @property
    def change_type(self):
        return self.__change_type


class SqlChange(Change):
    def __init__(self, order, comment, object_type, sql):
        Change.__init__(self, order, comment, object_type, SQL_CHANGE)
        self.__sql = sql

    @property
    def sql(self):
        return self.__sql
