"""
Looks at the upgrade operations for an entire set of upgrades, and constructs
a set of ordered micro changes necessary for the upgrade.

This creates a dependency tree that then has a topo sort run on it, but with
an added twist of non-dependent objects forced into following their order
number.  Use the "affects" and "depends" to help construct the proper ordering.

This requires correct construction of operations along with their ordering.
That is, if an upgrade changes the kind of index on a column, there should be
an implicit removal of the index, and the creation of the new index would
require a "depends" on the new removal operation.  The database implementation
would need to add this kind of logic, depending on how the database platform
handles these kinds of operations.
"""


from ..model.change import (SqlChange)
from ..model.schema import (SchemaObject, Order)


class UpgradeChange(object):
    """
    Represents a change to a SQL object.  This is only for the implied change
    that the schema generator must compute.

    FIXME move the "before" and "after" into the Order object.
    """
    def __init__(self, order: Order,
                 before: list or tuple, after: list or tuple):
        """
        :param before: things that must happen before this runs
        :param after: things that must happen after this runs
        :type before: list[str] or tuple[str]
        :type after: list[str] or tuple[str]
        """
        object.__init__(self)
        self.__order = order
        assert isinstance(order, Order)
        self.__before = tuple(before)
        for val in before:
            assert isinstance(val, str)
        self.__after = tuple(after)
        for val in after:
            assert isinstance(val, str)

    @property
    def order(self) -> Order:
        return self.__order

    @property
    def before(self) -> tuple:
        """
        Things that need to happen before this runs
        """
        return self.__before

    @property
    def after(self) -> tuple:
        """
        Things that need to happen after this runs
        """
        return self.__after


class TopLevelUpgradeChanges(object):
    """
    A group of upgrade changes associated with a single top-level schema object.
    These may include changes from other schema objects unrelated to the given
    top level object.

    The top-level object may be None if the changes are just SQL changes.
    """

    def __init__(self,
                 top_schema: SchemaObject or None,
                 changes: list or tuple):
        """
        :param top_schema:
        :param changes:
        :type changes: list[UpgradeChange] or tuple[UpgradeChange]
        """
        self.__top_schema = top_schema
        assert top_schema is None or isinstance(top_schema, SchemaObject)
        self.__changes = tuple(changes)
        for val in changes:
            assert isinstance(val, UpgradeChange)


class SqlUpgradeChange(UpgradeChange):
    """
    Low-level sql change.
    """
    def __init__(self, sql_change: SqlChange):
        UpgradeChange.__init__(self, sql_change.order, sql_change.affects,
                               sql_change.depends)
        assert isinstance(sql_change, SqlChange)
        self.__sql_change = sql_change

    @property
    def sql_change(self) -> SqlChange:
        return self.__sql_change


class AddSchemaChange(UpgradeChange):
    """
    Simple new schema object creation.
    """
    def __init__(self, schema_object: SchemaObject):

        # TODO foreign keys are marked as before?

        UpgradeChange.__init__(self, schema_object.order, [], [])
        assert isinstance(schema_object, SchemaObject)
        self.__schema_object = schema_object


class RemoveSchemaChange(UpgradeChange):
    """
    Simple removal of an existing object.
    """
    def __init__(self, schema_object: SchemaObject):
        UpgradeChange.__init__(self, schema_object.order, [], [])
