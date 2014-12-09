"""
Base classes used for the generation of code based on the model objects.
"""

from ..model.base import (SqlSet)
from ..model.schema import (SchemaObject, View, Table, Sequence, Procedure)
from ..model.change import (Change, SqlChange)
from .upgrade import (
    UpgradeAnalysis, TableUpgradeAnalysis, ViewUpgradeAnalysis,
    SequenceUpgradeAnalysis, ProcedureUpgradeAnalysis
)
from .upgrade_change import (TopLevelUpgradeChanges, UpgradeChange)


class UpgradeSchemaPlatformGenerator(object):
    """
    Base class for performing upgrades.
    """
    def generate_sql(self, top_object: TopLevelUpgradeChanges) -> list:
        """
        :rtype: list[str]
        """
        raise NotImplemented("abstract class")


class NewSchemaPlatformGenerator(object):
    """
    Base class for creating a new schema.
    """
    def generate_sql(self, top_object: SchemaObject) -> list:
        """
        :rtype: list[str]
        """
        raise NotImplemented("abstract class")


class SchemaScriptGenerator(object):
    """
    Base class for the generation of sql scripts.  The methods should be
    stateless.
    """

    def __init__(self):
        object.__init__(self)

    def is_platform(self, platforms: list or tuple) -> bool:
        """
        Checks if this generator is one of the supported platform grammars.
        The "platforms" variable is produced by the Change.platforms property.

        :type platforms: list[str] or tuple[str]
        :rtype: boolean
        """
        raise NotImplementedError("not implemented")

    def _get_sql_for_platform(self, sql_set: SqlSet) -> str:
        raise NotImplementedError()

    def generate_base(self, top_object) -> list:
        """

        :param top_object:
        :rtype: list[str]
        """
        if isinstance(top_object, SchemaObject):
            return self._generate_base_schema(top_object)
        elif isinstance(top_object, Change):
            # Nothing to do for the generation of the base schema with
            # a change
            return []
        else:
            raise Exception("Cannot generate schema with " + str(top_object))

    def generate_upgrade(
            self, change: UpgradeChange) -> list:
        """
        :rtype: list[str]
        """
        if isinstance(change, SqlChange):
            return self._generate_upgrade_sqlchange(change)
        elif isinstance(change, UpgradeAnalysis):
            return self._generate_upgrade_schema(change)
        else:
            raise Exception("Cannot generate upgrade schema with " +
                            str(change))

    def _generate_base_schema(self, top_object) -> list:
        """
        Generates the "creation" script for a given schema object.  It does
        not produce the upgrade script.

        :param top_object:
        :rtype: list[str]
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

    def _generate_upgrade_schema(self, change: UpgradeAnalysis) -> list:
        """
        Generate the upgrade schema for a SchemaObject.

        :rtype: list[str]
        """

        if not change.has_changes():
            return []

        # FIXME this should instead be taking a series of abstract changes,
        # and converting those.

        if isinstance(change, TableUpgradeAnalysis):
            return self._generate_upgrade_table(change)
        elif isinstance(change, ViewUpgradeAnalysis):
            return self._generate_upgrade_view(change)
        elif isinstance(change, SequenceUpgradeAnalysis):
            return self._generate_upgrade_sequence(change)
        elif isinstance(change, ProcedureUpgradeAnalysis):
            return self._generate_upgrade_procedure(change)
        else:
            raise Exception("unknown schema " + str(change))

    def _generate_base_table(self, table: Table) -> list:
        """
        Generate the creation script for a Table.

        :param table:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_base_view(self, view: View) -> list:
        """
        Generate the creation script for a View.

        :param view:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_base_sequence(self, sequence: Sequence) -> list:
        """
        Generate the creation script for a Sequence.

        :param sequence:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_base_procedure(self, procedure: Procedure) -> list:
        """
        Generate the creation script for a Procedure.

        :param procedure:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_sqlchange(self, sql_change: SqlChange) -> list:
        """
        Generates the upgrade sql for a SqlChange object.  This can be called
        if the platforms don't match.

        Default implementation just returns the sql text.

        :param sql_change:
        :rtype: list[str]
        """
        if self.is_platform(sql_change.sql_set.platforms):
            return [self._get_sql_for_platform(sql_change.sql_set)]
        else:
            return []

    def _generate_upgrade_table(self, table: TableUpgradeAnalysis) -> list:
        """
        Generate the upgrade script for a Table.

        :param table:
        :rtype: list[str]
        """

        # Need to be careful here.  Constraint removal needs to happen first,
        # followed by column removal, then column rename, then column add,
        # then the remaining constraint changes.

        ret = []
        for top_change_list in table.change_categories.values():
            for top_change in top_change_list:
                ret.extend(self._generate_upgrade_table_change(
                    table, top_change))

        for constraint in table.constraints:
            for change in constraint.changes:
                ret.extend(self._generate_upgrade_table_constraint(table,
                           constraint, change))

        return ret

    def _generate_upgrade_table_change(
            self, table: TableUpgradeAnalysis, change: Change):
        raise NotImplementedError("not implemented")

    def _generate_upgrade_table_constraint(self, table, constraint, change):
        raise NotImplementedError("not implemented")

    def _generate_upgrade_view(self, view: ViewUpgradeAnalysis) -> list:
        """
        Generate the upgrade script for a View.

        :param view:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_sequence(
            self, sequence: SequenceUpgradeAnalysis) -> list:
        """
        Generate the upgrade script for a Sequence.

        :param sequence:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")

    def _generate_upgrade_procedure(
            self, procedure: ProcedureUpgradeAnalysis) -> list:
        """
        Generate the upgrade script for a Procedure.

        :param procedure:
        :rtype: list[str]
        """
        raise NotImplementedError("not implemented")
