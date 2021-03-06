"""
Classes that encompass changes to the schema.  Changes are associated with
a version's schema.  All the changes should migrate the database from the
previous version to the current version.
"""

from .base import (BaseObject, SqlSet, Order)


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
ORDER_CHANGE = ChangeType('order')
SQL_CHANGE = ChangeType('sql')
CHANGE_TYPES = (ADD_CHANGE, REMOVE_CHANGE, RENAME_CHANGE, ALTER_CHANGE,
                SQL_CHANGE, ORDER_CHANGE)

# Not in the list of normal change types
ERROR_CHANGE_TYPE = ChangeType('error')


class Change(BaseObject):
    """
    A single change to a schema object.  It can either be top-level
    (i.e. drop a table) or within a schema object (i.e. rename a table).

    These do not need to be specified for the creation of an object.

    Non-trivial changes require a sql change.  Trivial changes use the
    SchemaChange object.
    """
    def __init__(self, order, comment, object_type, change_type):
        BaseObject.__init__(self, order, comment, object_type)
        assert isinstance(change_type, ChangeType)
        self.__change_type = change_type

    @property
    def change_type(self) -> ChangeType:
        """
        The kind of change being performed.  Must be one of the pre-defined
        CHANGE_TYPES.
        """
        return self.__change_type


class SchemaChange(Change):
    """
    A simple change to a schema object that doesn't require an explicit SQL
    instruction to perform the change.

    Note that this simply defines the change to perform, and on what object
    the change happens.  It does not contain information about the previous
    version that the change affects.

    For rename and remove changes, a `previous_name` must be given.
    """
    def __init__(self, order, comment, object_type, change_type, previous_name):
        after = list(order.occurs_after)
        if previous_name is not None and previous_name not in after:
            after.append(previous_name)
        order = Order(order.items(), order.occurs_before, after)
        Change.__init__(self, order, comment, object_type, change_type)
        self.__previous_name = previous_name
        if change_type in [REMOVE_CHANGE, RENAME_CHANGE]:
            assert previous_name is not None
        else:
            assert previous_name is None

    @property
    def previous_name(self):
        """
        The name of the object changed.  Is only not None when the change type
        is remove or rename.
        """
        return self.__previous_name


class SqlChange(Change):
    """
    An explicit set of SQL instructions to run to perform the change.
    """
    def __init__(self, order, comment, object_type, sql_set):
        Change.__init__(self, order, comment, object_type, SQL_CHANGE)
        assert isinstance(sql_set, SqlSet)
        self.__sql_set = sql_set

    @property
    def sql_set(self):
        """

        :return: SqlSet
        """
        return self.__sql_set

    def __repr__(self):
        return (
            "SqlChange(order={}, comment={}, object_type={}, " +
            "sql_set={})".format(
                self.order, self.comment, self.object_type, self.sql_set)
        )
