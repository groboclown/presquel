"""
Base classes used for the generation of code based on the model objects.
"""

from ..model.schema import (SchemaObject, View, Table, Sequence, Procedure)
from ..model.change import (Change, SqlChange)
from .upgrade import (UpgradeAnalysis)


class SchemaScriptGenerator(object):
    """
    Base class for the generation of sql scripts.  The methods should be
    stateless.
    """

    def __init__(self):
        object.__init__(self)

    def is_platform(self, platforms):
        """
        Checks if this generator is one of the supported platform grammars.
        The "platforms" variable is produced by the Change.platforms property.

        :param platforms:
        :return: boolean
        """
        raise NotImplementedError("not implemented")

    def generate_base(self, top_object):
        """

        :param top_object:
        :return: list(str)
        """
        if isinstance(top_object, SchemaObject):
            return self._generate_base_schema(top_object)
        elif isinstance(top_object, Change):
            # Nothing to do for the generation of the base schema with
            # a change
            return []
        else:
            raise Exception("Cannot generate schema with " + str(top_object))

    def generate_upgrade(self, top_object, previous_version):
        """

        :param top_object:
        :return: list(str)
        """
        if isinstance(top_object, SchemaObject):
            return self._generate_upgrade_schema(top_object, previous_version)
        elif isinstance(top_object, SqlChange):
            assert previous_version is None
            return self._generate_upgrade_sqlchange(top_object)
        else:
            raise Exception("Cannot generate upgrade schema with " +
                            str(top_object))

    def _generate_base_schema(self, top_object):
        """
        Generates the "creation" script for a given schema object.  It does
        not produce the upgrade script.

        :param top_object:
        :return: list(str)
        """
        if isinstance(top_object, Table):
            return self._generate_base_table(top_object)
        elif isinstance(top_object, View):
            return self._generate_base_view(top_object)
        elif isinstance(top_object, Sequence):
            return self._generate_base_sequence(top_object)
        elif isinstance(top_object, Procedure):
            return self._generate_base_procedure(top_object)
        else:
            raise Exception("unknown schema " + str(top_object))

    def _generate_upgrade_schema(self, top_object):
        """
        Generate the upgrade schema for a SchemaObject.

        :param top_object:
        :return: list(str)
        """
        if isinstance(top_object, Table):
            return self._generate_upgrade_table(top_object)
        elif isinstance(top_object, View):
            return self._generate_upgrade_view(top_object)
        elif isinstance(top_object, Sequence):
            return self._generate_upgrade_sequence(top_object)
        elif isinstance(top_object, Procedure):
            return self._generate_upgrade_procedure(top_object)
        else:
            raise Exception("unknown schema " + str(top_object))

    def _generate_base_table(self, table):
        """
        Generate the creation script for a Table.

        :param table:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_base_view(self, view):
        """
        Generate the creation script for a View.

        :param view:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_base_sequence(self, sequence):
        """
        Generate the creation script for a Sequence.

        :param sequence:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_base_procedure(self, procedure):
        """
        Generate the creation script for a Procedure.

        :param procedure:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_sqlchange(self, sql_change):
        """
        Generates the upgrade sql for a SqlChange object.  This can be called
        if the platforms don't match.

        Default implementation just returns the sql text.

        :param sql_change:
        :return: list(str)
        """
        if self.is_platform(sql_change.platforms):
            return [sql_change.sql]
        else:
            return []

    def _generate_upgrade_table(self, table):
        """
        Generate the upgrade script for a Table.

        :param table:
        :return: list(str)
        """
        ret = []
        for top_change in table.changes:
            ret.extend(self._generate_upgrade_table_change(table, top_change))



        for constraint in table.constraints:
            for change in constraint.changes:
                ret.extend(self._generate_upgrade_table_constraint(table,
                           constraint, change))

        raise NotImplementedError("not implemented")

    def _generate_upgrade_table_change(self, table, change):
        raise NotImplementedError("not implemented")

    def _generate_upgrade_table_constraint(self, table, constraint, change):
        raise NotImplementedError("not implemented")

    def _generate_upgrade_view(self, view):
        """
        Generate the upgrade script for a View.

        :param view:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_sequence(self, sequence):
        """
        Generate the upgrade script for a Sequence.

        :param sequence:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_procedure(self, procedure):
        """
        Generate the upgrade script for a Procedure.

        :param procedure:
        :return: list(str)
        """
        raise NotImplementedError("not implemented")
