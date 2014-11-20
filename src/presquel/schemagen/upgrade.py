"""
Inspects the schema between a previous and a current version.
"""

from ..model.base import (VIEW_TYPE, TABLE_TYPE, COLUMN_TYPE)
from ..model.schema import (
    SchemaObject, Column, Table, View, Constraint, ColumnarSchemaObject)
from ..model.change import (
    Change, SchemaChange, SqlChange, REMOVE_CHANGE,
    ADD_CHANGE, RENAME_CHANGE, ALTER_CHANGE, SQL_CHANGE, CHANGE_TYPES,
    ChangeType)


class UpgradeAnalysisProblem(object):
    """
    A problem discovered in the analysis of the upgrade definition
    """
    def __init__(self, obj: object, message: str):
        self.__obj = obj
        self.__message = message

    @property
    def obj(self) -> object:
        return self.__obj

    @property
    def message(self) -> str:
        return self.__message

    def __str__(self):
        return self.message + ': ' + str(self.obj)

    def __repr__(self):
        return ("UpgradeAnalysisProblem(" + repr(self.obj) + ", " +
                repr(self.message) + ")")


class UpgradeAnalysis(object):
    """
    General parent class that analyzes the before and after upgrade versions
    of a schema object.

    Analysis objects are always based on the "after" object.  If an object
    moves from a table to a view, the analysis will be a View.
    """
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change or None):
        object.__init__(self)

        assert before is None or isinstance(before, SchemaObject)
        assert (after is None or isinstance(after, SchemaObject) or
                (isinstance(after, Change) and
                 after.change_type == REMOVE_CHANGE))
        assert not (before is None and after is None)

        self._warnings = []
        self._errors = []
        self._incompatible = []

        changes = []
        if after is None:
            self._warnings.append(
                UpgradeAnalysisProblem(before, 'implicit removal of object'))
        elif isinstance(after, Change):
            changes.append(after)
        else:
            assert isinstance(after, SchemaObject)
            changes.extend(after.changes)

        if after is None or isinstance(after, Change):
            self.__constraint_changes = SchemaUpgradedSet(
                before.constraints, [])
        elif before is None:
            self.__constraint_changes = SchemaUpgradedSet(
                [], after.constraints)
        else:
            self.__constraint_changes = SchemaUpgradedSet(
                before.constraints, after.constraints)

        self.__before = before
        self.__after = after
        self.__changes = _categorize_changes(changes)

        # General checks for changes
        # The main categories can only have at most 1 of them in total.
        # Note that alter and sql can be numerous.
        big_change_count = 0
        for cat in (ADD_CHANGE, REMOVE_CHANGE, RENAME_CHANGE):
            count = len(self.change_categories[cat])
            big_change_count += count
            if count > 1:
                self._errors.append(
                    UpgradeAnalysisProblem(
                        after, 'at most 1 ' + str(cat) + ' is allowed'))

        if (big_change_count > 1 or (
                big_change_count > 0 and
                len(self.change_categories[ALTER_CHANGE]) +
                len(self.change_categories[SQL_CHANGE]) > 0)):
            self._errors.append(
                UpgradeAnalysisProblem(
                    after,
                    'at most 1 of an add, remove, or rename is allowed, and ' +
                    'it cannot be done with an alter or sql change'))

        if before is None:
            if len(self.change_categories[ADD_CHANGE]) <= 0:
                self._warnings.append(
                    UpgradeAnalysisProblem(after, 'implicit add'))
            if (len(self.change_categories[REMOVE_CHANGE]) > 0 or
                    len(self.change_categories[RENAME_CHANGE]) > 0 or
                    len(self.change_categories[ALTER_CHANGE]) > 0):
                self._errors.append(
                    UpgradeAnalysisProblem(
                        after,
                        'can only add due to no previous version found'))

    @property
    def before(self) -> tuple or None:
        """
        The version of the object before upgrade.

        :rtype: None or tuple[SchemaObject]
        """
        return self.__before

    @property
    def after(self) -> tuple:
        """
        The version of the object after upgrading.

        :rtype: None or tuple[SchemaObject or Change]
        """
        return self.__after

    @property
    def change_categories(self) -> dict:
        """
        All the top-level changes defined by after, sorted by change type.

        If the "after" object has sub-schema, those may have their own changes.

        :rtype: dict[ChangeType, list[Change]]
        """
        return self.__changes

    @property
    def errors(self) -> tuple:
        """
        Errors in the upgrade definition.

        :rtype: tuple[UpgradeAnalysisProblem]
        """
        return tuple(self._errors)

    @property
    def warnings(self) -> tuple:
        """
        Warnings in the upgrade definition.

        :rtype: tuple[UpgradeAnalysisProblem]
        """
        return tuple(self._warnings)

    @property
    def incompatible(self) -> tuple:
        """
        Changes that could potentially cause incompatibility on the software
        side.

        :rtype: tuple[Change]
        """
        return tuple(self._incompatible)

    @property
    def constraint_changes(self) -> tuple:
        """
        Change set for all the constraints.

        :rtype: tuple[Constraint]
        """
        return self.__constraint_changes


class SchemaUpgradedSet(object):
    """
    Matches the upgrade for a set of schema objects.  This only makes sense
    for top-level objects and columns.
    """

    def __init__(self, before_set, after_set):
        object.__init__(self)

        before_names = {}
        upgrades = []
        self.__errors = []
        duplicate_names = []
        stand_alone_changes = []

        for obj in before_set:
            # These must all be schema objects
            assert isinstance(obj, SchemaObject)
            if obj.full_name in before_names:
                self.__errors.append(
                    UpgradeAnalysisProblem(obj, 'duplicate name'))
                if before_names[obj.full_name] not in duplicate_names:
                    self.__errors.append(UpgradeAnalysisProblem(
                        before_names[obj.full_name], 'duplicate name'))
            else:
                before_names[obj.full_name] = obj

        for obj in after_set:
            if isinstance(obj, SchemaChange):
                if obj.change_type == REMOVE_CHANGE:
                    if obj.previous_name in before_names:
                        upgrades.append(
                            SchemaUpgradedSet._create_upgrade_schema(
                                before_names[obj.previous_name], obj))
                        del before_names[obj.previous_name]
                    else:
                        self.__errors.append(UpgradeAnalysisProblem(
                            obj, 'remove change has no known previous object'))
                else:
                    # Should this look at "affects"?
                    stand_alone_changes.append(obj)
            elif isinstance(obj, SqlChange):
                # Should this look at "affects"?
                stand_alone_changes.append(obj)
            elif isinstance(obj, SchemaObject):
                change_types = _categorize_changes(obj.changes)
                name = obj.full_name
                if len(change_types[RENAME_CHANGE]) > 0:
                    # more than one is an error, but we're not checking that now
                    name = change_types[RENAME_CHANGE][0].previous_name

                if name in before_names:
                    before = before_names[name]
                    upgrades.append(
                        SchemaUpgradedSet._create_upgrade_schema(before, obj))
                    del before_names[name]
                else:
                    upgrades.append(
                        SchemaUpgradedSet._create_upgrade_schema(None, obj))
            else:
                assert False, "invalid object " + repr(obj)

        for before in before_names.values():
            upgrades.append(
                SchemaUpgradedSet._create_upgrade_schema(before, None))

        self.__upgrades = tuple(upgrades)
        self.__stand_alone_changes = tuple(stand_alone_changes)

    @property
    def errors(self) -> list:
        """
        List of issues with the set of changes.

        :rtype: list[UpgradeAnalysisProblem]
        """
        return self.__errors

    @property
    def stand_alone_changes(self) -> list:
        """
        A list of changes that have no corresponding previous object.

        :rtype: list[Change]
        """
        return self.__stand_alone_changes

    @property
    def upgrades(self) -> list:
        """
        A list of UpgradeAnalysis objects

        :rtype: list[UpgradeAnalysis]
        """
        return self.__upgrades

    @staticmethod
    def _create_upgrade_schema(before, after) -> UpgradeAnalysis:
        if before is None:
            assert isinstance(after, SchemaObject)

            if isinstance(after, Table):
                return TableUpgradeAnalysis(None, after)
            if isinstance(after, View):
                return ViewUpgradeAnalysis(None, after)
            if isinstance(after, Column):
                return ColumnUpgradeAnalysis(None, after)

            raise Exception("Don't know how to upgrade a " +
                            after.object_type + " (" + str(after) + ")")
        elif after is None:
            assert isinstance(before, SchemaObject)

            if isinstance(before, Table):
                return TableUpgradeAnalysis(before, None)
            if isinstance(before, View):
                return ViewUpgradeAnalysis(before, None)
            if isinstance(before, Column):
                return ColumnUpgradeAnalysis(before, None)

            raise Exception("Don't know how to remove a " +
                            before.object_type + " (" + str(before) + ")")
        else:
            # FIXME
            pass


class IncompatibleUpgradeAnalysis(UpgradeAnalysis):
    """
    An upgrade that simply won't work, such as renaming a table into a
    stored procedure.  This indicates that the upgrade requires a more
    refined approach.
    """
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change):
        UpgradeAnalysis.__init__(self, before, after)
        self._errors.append(UpgradeAnalysisProblem(after,
                            'incompatible upgrade'))


class ColumnarUpgradeAnalysis(UpgradeAnalysis):
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change or None):
        UpgradeAnalysis.__init__(self, before, after)

        # If a change is for a non-columnar schema to columnar, or vice-versa,
        # use IncompatibleUpgradeAnalysis instead
        assert before is None or isinstance(before, ColumnarSchemaObject)
        assert (after is None or isinstance(after, SchemaChange) or
                isinstance(after, ColumnarSchemaObject))

        column_upgrades = None

        if (after is not None and before is not None and
                isinstance(after, ColumnarSchemaObject)):
            after_set = list(after.columns)
            for change in after.changes:
                if change.object_type == COLUMN_TYPE:
                    after_set.append(change)
            column_upgrades = SchemaUpgradedSet(before.columns, after_set)
            self._errors.extend(column_upgrades.errors)
            self._check_column_problems(column_upgrades)

        self.__column_upgrades = column_upgrades

        # FIXME match top-changes with other metadata.

    @property
    def column_upgrade_set(self) -> SchemaUpgradedSet:
        """
        a SchemaUpgradedSet for the columns.  Will be None if one of the
        two base schema objects is None.
        """
        return self.__column_upgrades

    def _check_column_problems(self, column_upgrades: SchemaUpgradedSet):
        for change in column_upgrades.stand_alone_changes:
            # The changes in this list:
            #  * have a object_type of column
            #  * are not "remove"
            #  * are not associated with an "after" column.
            # So, unless these are an explicit Sql change, they should be
            # invalid.
            if not isinstance(change, SqlChange):
                self._errors.append(
                    UpgradeAnalysisProblem(change, 'invalid columnar change'))

        for analysis in column_upgrades.upgrades:
            assert isinstance(analysis, UpgradeAnalysis)
            # Push the problems up to the top
            self._errors.extend(analysis.errors)
            self._warnings.extend(analysis.warnings)


class ViewUpgradeAnalysis(ColumnarUpgradeAnalysis):
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change or None):
        ColumnarUpgradeAnalysis.__init__(self, before, after)
        assert before is None or isinstance(before, SchemaObject)

        if before is not None and before.object_type != VIEW_TYPE:
            self._errors.append(UpgradeAnalysisProblem(
                before, 'cannot upgrade directly from a ' +
                before.object_type + ' to a view'))


class TableUpgradeAnalysis(ColumnarUpgradeAnalysis):
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change or None):
        ColumnarUpgradeAnalysis.__init__(self, before, after)
        assert before is None or isinstance(before, SchemaObject)

        if before is not None and before.object_type != TABLE_TYPE:
            self._errors.append(UpgradeAnalysisProblem(
                before, 'cannot upgrade directly from a ' +
                before.object_type + ' to a table'))


class ColumnUpgradeAnalysis(UpgradeAnalysis):
    def __init__(self, before: SchemaObject or None,
                 after: SchemaObject or Change or None):
        UpgradeAnalysis.__init__(self, before, after)

        # A column type cannot have the "before" be anything other than a
        # column

        assert before is None or isinstance(before, Column)
        assert (after is None or isinstance(after, Column) or
                isinstance(after, SchemaChange))

        if after is SchemaChange or after is None:
            # implicit removal, due to parent class check
            # FIXME do something with this
            pass


def _categorize_changes(changes: tuple or list) -> dict:
    """
    Organize the list of changes by grouping them into change types.

    :type changes: tuple[Change] or list[Change]
    :rtype: dict[ChangeType, list[Change]]
    """
    ret = {}
    for change_type in CHANGE_TYPES:
        ret[change_type] = []
    for change in changes:
        assert isinstance(change, Change)
        ret[change.change_type].append(change)
    return ret
