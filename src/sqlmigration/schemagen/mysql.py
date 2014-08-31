"""
Base classes used for the generation of code based on the model objects.
"""

from ..model import (ValueTypeValue, View, Table, SqlString, SqlSet, Constraint,
                     NamedConstraint, SqlConstraint, LanguageConstraint)
from .base import (SchemaScriptGenerator)
import time

PLATFORMS = ('mysql',)


class MySqlScriptGenerator(SchemaScriptGenerator):
    """
    Generates MySql syntax for schema generation.
    """

    def __init__(self):
        SchemaScriptGenerator.__init__(self)

    def is_platform(self, platforms):
        """
        Checks if this generator is one of the supported platform grammars.
        The "platforms" variable is produced by the Change.platforms property.

        :param platforms:
        :return: boolean
        """
        for p in platforms:
            if p.strip().lower() in PLATFORMS:
                return True
        return False

    def _header(self, schema_object):
        return '-- Schema for ' + schema_object.name + \
               '\n-- Generated on ' + time.asctime(time.gmtime(time.time())) + \
               '\n\n'

    def _generate_base_table(self, table):
        """
        Generate the creation script for a Table.

        http://dev.mysql.com/doc/refman/5.1/en/create-table.html

        :param table: Table
        :return: list(str)
        """
        assert isinstance(table, Table)

        # Note: do not use "IF NOT EXISTS", because that indicates upgrade.
        constraint_sql = ''
        sql = 'CREATE TABLE '
        if table.catalog_name:
            sql += _parse_name(table.catalog_name) + '.'
        if table.schema_name:
            sql += _parse_name(table.schema_name) + '.'
        sql += _parse_name(table.table_name)
        # Tablespace used?

        sql += ' (\n'
        first = True
        for col in table.columns:
            if first:
                first = False
                sql += '    '
            else:
                sql += '\n    , '
            sql += _parse_name(col.name) + ' ' + _parse_value_type(
                col.value_type)

            for ct in col.constraints:
                if ct.constraint_type == 'notnull':
                    sql += ' NOT NULL'
                elif (ct.constraint_type == 'nullable' or
                        ct.constraint_type == 'null'):
                    # print("null constraint")
                    sql += ' NULL'

            if col.default_value is not None:
                sql += ' DEFAULT ' + _escape_value_type_value(col.default_value)

            if col.auto_increment:
                sql += ' AUTO_INCREMENT'

            # TODO add COMMENT, COLUMN_FORMAT, STORAGE support
            for ct in col.constraints:
                constraint_sql += _generate_base_constraints(
                    table, [col], ct)

        # FIXME add clustered index table constraint checking

        for ct in table.constraints:
            assert isinstance(ct, Constraint)
            constraint_sql += _generate_base_constraints(
                table, ct.get_columns_by_names(table), ct)

        sql += constraint_sql + '\n)'

        # FIXME add table options

        # FIXME add partition options

        # FIXME make this selectable.  For now, we'll hard-code it for the
        # foreign key support.
        sql += ' ENGINE=INNODB;\n'

        return [self._header(table), sql]

    def _generate_base_view(self, view):
        """
        Generate the creation script for a View.

        :param view:
        :return: list(str)
        """
        assert isinstance(view, View)

        sql = 'CREATE '
        if view.replace_if_exists:
            sql += 'OR REPLACE '
        sql_string = view.select_query.get_for_platform('mysql')
        if sql_string is None:
            raise Exception("no mysql support for view " + view.name)
        assert isinstance(sql_string, SqlString)
        sql += 'VIEW ' + view.name + ' AS\n' + sql_string.sql + ';\n'
        return [self._header(view), sql]

    def _generate_base_sequence(self, sequence):
        """
        Generate the creation script for a Sequence.

        :param sequence:
        :return: list(str)
        """
        raise Exception("not implemented")

    def _generate_base_procedure(self, procedure):
        """
        Generate the creation script for a Procedure.

        :param procedure:
        :return: list(str)
        """
        raise Exception("not implemented")

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
        raise Exception("not implemented")

    def _generate_upgrade_view(self, view):
        """
        Generate the upgrade script for a View.

        :param view:
        :return: list(str)
        """
        raise Exception("not implemented")

    def _generate_upgrade_sequence(self, sequence):
        """
        Generate the upgrade script for a Sequence.

        :param sequence:
        :return: list(str)
        """
        raise Exception("not implemented")

    def _generate_upgrade_procedure(self, procedure):
        """
        Generate the upgrade script for a Procedure.

        :param procedure:
        :return: list(str)
        """
        raise Exception("not implemented")


def _escape_value_type_value(vtv):
    """

    :param vtv: ValueTypeValue
    :return: str
    """
    assert isinstance(vtv, ValueTypeValue)

    if vtv.str_value is not None:
        # FIXME look at proper escaping
        return "'" + vtv.str_value.replace("'", "''")
    elif vtv.boolean_value is not None:
        if vtv.boolean_value:
            return "1"
        else:
            return "0"
    elif vtv.computed_value is not None:
        return str(vtv.computed_value)
    elif vtv.date_value is not None:
        # FIXME see if we need proper conversion here
        return str(vtv.date_value)
    elif vtv.numeric_value is not None:
        return str(vtv.numeric_value)
    else:
        return 'NULL'


def _parse_value_type(value_type):
    return value_type.strip().upper()


def _parse_name(name):
    # TODO properly escape the name
    return name.strip()


def _parse_index_option(option):
    # TODO properly parse the option; for now, assume it's a string
    if isinstance(option, str):
        return option.strip()
    else:
        raise Exception("can only parse string index options")


def _generate_base_constraints(table, columns, ct):
    assert isinstance(ct, Constraint)
    constraint_sql = ''
    column_names = ','.join(
        [_parse_name(column.name) for column in columns])
    assert isinstance(ct, Constraint)
    if isinstance(ct, LanguageConstraint):
        # code generation constraint, not used in schema generation
        return ''
    if isinstance(ct, SqlConstraint):
        # For all the additional stuff that this tool doesn't
        # support
        if ct.constraint_type == 'native':
            s = ct.sql
            assert isinstance(s, SqlSet)
            return ('\n    , ' +
                    s.get_for_platform(PLATFORMS).sql)
        return ''

    name = None
    if isinstance(ct, NamedConstraint):
        name = ct.name

    if ct.constraint_type == 'fulltextindex':
        assert name is not None
        constraint_sql += ('\n    , FULLTEXT INDEX ' + name + ' (' +
                           column_names + ')')
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'spatialindex':
        assert name is not None
        constraint_sql += '\n    , SPATIAL INDEX ' + name + \
                          ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'uniqueindex':
        if name is None:
            raise Exception("No name defined for unique index")
        constraint_sql += '\n    , CONSTRAINT ' + name + \
                          ' UNIQUE INDEX'
        if 'using' in ct.details:
            constraint_sql += ' USING ' + ct.details['using']
        constraint_sql += ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'index':
        assert name is not None
        constraint_sql += '\n    , INDEX ' + name
        if 'using' in ct.details:
            constraint_sql += ' USING ' + ct.details['using']
        constraint_sql += ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'fulltextkey':
        assert name is not None
        constraint_sql += '\n    , FULLTEXT KEY ' + name + \
                          ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'spatialkey':
        assert name is not None
        constraint_sql += '\n    , SPATIAL KEY ' + name + \
                          ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'primarykey':
        assert name is not None
        constraint_sql += '\n    , CONSTRAINT ' + name + \
                          ' PRIMARY KEY'
        if 'using' in ct.details:
            constraint_sql += 'USING ' + ct.details['using']
        constraint_sql += ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'uniquekey':
        assert name is not None
        constraint_sql += '\n    , CONSTRAINT ' + name + \
                          ' UNIQUE KEY'
        if 'using' in ct.details:
            constraint_sql += ' USING ' + ct.details['using']
        constraint_sql += ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'key':
        assert name is not None
        constraint_sql += '\n    , KEY ' + name
        if 'using' in ct.details:
            constraint_sql += ' USING ' + ct.details['using']
        constraint_sql += ' (' + _parse_name(column_names) + ')'
        if 'option' in ct.details:
            constraint_sql += ' ' + _parse_index_option(
                ct.details['option'])

    elif ct.constraint_type == 'foreignkey':
        assert name is not None
        if (('column' not in ct.details and
                'columns' not in ct.details) or
                'table' not in ct.details):
            raise Exception("column and table must be in foreign "
                            "key; found in " + column_names + " in " +
                            table.table_name)
        constraint_sql += '\n    , FOREIGN KEY ' + name + ' (' + \
                          _parse_name(column_names) + \
                          ') REFERENCES ' + \
                          _parse_name(ct.details['table']) + ' ('
        if 'column' in ct.details:
            constraint_sql += _parse_name(ct.details['column'])
        elif 'columns' in ct.details:
            constraint_sql += ",".join(
                _parse_name(fc) for fc in ct.details['columns'])
        else:
            raise Exception("no column definition for foreignkey")
        constraint_sql += ')'

        if 'match' in ct.details:
            # TODO details value should be FULL, PARTIAL, or SIMPLE
            constraint_sql += ' MATCH ' + ct.details[
                'match'].upper()
        if 'delete' in ct.details:
            # TODO option should be RESTRICT, CASCADE, SET NULL,
            # or NO ACTION
            constraint_sql += ' ON DELETE ' + ct.details[
                'delete'].upper()
        if 'update' in ct.details:
            # TODO option should be RESTRICT, CASCADE, SET NULL,
            # or NO ACTION
            constraint_sql += ' ON UPDATE ' + ct.details[
                'update'].upper()

            # We allow other constraint types, because those could be used
            # by other databases or tools.
    return constraint_sql
