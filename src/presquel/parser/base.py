
from ..model.change import (
    Change, SchemaChange, SqlChange, ChangeType, CHANGE_TYPES, SQL_CHANGE,
    ERROR_CHANGE_TYPE)
from ..model.base import (
    SCHEMA_OBJECT_TYPES, TABLE_TYPE, VIEW_TYPE, CONSTRAINT_TYPE, COLUMN_TYPE,
    SqlString, SqlArgument, BaseObject, SchemaObjectType)
from ..model.schema import (
    Table, View, SchemaObject,
    Column, SqlConstraint, LanguageConstraint, Constraint,
    NamedConstraint, WhereClause, ExtendedSql,
    ValueTypeValue, SqlSet, LanguageSet)
from ..model.version import (
    ErrorObject, FATAL_TYPE, ERROR_TYPE, WARNING_TYPE, NOTE_TYPE
)
from collections import (Iterable)


class BaseObjectBuilder(object):
    def __init__(self, parser: object):
        """
        :type parser: SchemaParser
        """
        assert isinstance(parser, SchemaParser)
        object.__init__(self)
        self._parser = parser
        self.order = parser.next_order()
        self.comment = None
        self.__problems = []

    def parse(self, key, val):
        if key == 'error':
            self.problem(str(val), ERROR_TYPE)
        elif key == 'warning':
            self.problem(str(val), WARNING_TYPE)
        elif key == 'note':
            self.problem(str(val), NOTE_TYPE)
        elif key == 'comment':
            self.comment = self.to_str(key, val).strip()
        elif key == 'order':
            self.order = self._parser.next_explicit_order(int(val))
        else:
            return False
        return True

    def finish(self, obj: BaseObject):
        for problem in self.__problems:
            problem.set_source(obj)
        return obj

    def to_str(self, key, val):
        if isinstance(val, str):
            return val
        if isinstance(val, int) or isinstance(val, float):
            return str(val)
        else:
            self.problem(str(key) + ' expected string value, found ' + str(val),
                         # Should this be a warning?
                         ERROR_TYPE)
            return str(val)

    def to_int(self, key, val):
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(float)
        if isinstance(val, str) and val.isdecimal():
            return int(val)
        else:
            self.problem(str(key) + ' expected int value, found ' + str(val),
                         # Should this be a warning?
                         ERROR_TYPE)
            return 0

    def to_schema_type(self, key: str, type_name) -> SchemaObjectType:
        converted_type_name = self.to_str('type', type_name).strip().lower()
        for t in SCHEMA_OBJECT_TYPES:
            if t.name == converted_type_name:
                return t
        self.problem(key + ": unknown schema object type: " + repr(type_name),
                     ERROR_TYPE)
        return ERROR_TYPE

    def to_change_type(self, key: str, type_name) -> ChangeType:
        converted_type_name = self.to_str('type', type_name).strip().lower()
        for t in CHANGE_TYPES:
            if t.name == converted_type_name:
                return t
        self.problem(key + ": unknown change type: " + repr(type_name),
                     ERROR_TYPE)
        return ERROR_CHANGE_TYPE

    def to_boolean(self, key, val) -> bool:
        if val is True or val is False:
            return val
        if isinstance(val, int):
            return val != 0
        if not isinstance(val, str):
            self.problem(key + ': expected boolean value, found ' + repr(val),
                         WARNING_TYPE)
        val = str(val).strip().lower()
        if val in ["1", "true", "on", "yes", "t"]:
            return True
        if val in ["0", "false", "off", "no", "f"]:
            return False
        self.problem(key + ' expected a recognized boolean phrase, but found ' +
                     val + '; assuming false', WARNING_TYPE)
        return False

    def unknown_key(self, key, val):
        self.problem("unknown key (" + key + ") set to " + repr(val),
                     WARNING_TYPE)

    def problem(self, message, level: SchemaObjectType):
        problem = self._parser.problem(message, level)
        self.__problems.append(problem)
        return problem

    def _fail_on(self, key, val):
        """
        Create a failure error for this key / value.
        """
        self.problem('unknown key (' + str(key) + ') set to ' + repr(val),
                     ERROR_TYPE)


class NameSpaceObjectBuilder(BaseObjectBuilder):
    def __init__(self, parser: object, name_keys, change_type,
                 is_readonly: bool):
        """
        :type parser: SchemaParser
        """
        BaseObjectBuilder.__init__(self, parser)
        self.catalog_name = None
        self.schema_name = None
        self.name = None
        self.table_space = None
        self.constraints = []
        self.changes = []
        self.__name_keys = name_keys
        self.__change_type = change_type
        self.__is_readonly = is_readonly

    def parse(self, key, val):
        if BaseObjectBuilder.parse(self, key, val):
            return True
        if key == 'change':
            self.changes.append(self._parser.parse_inner_change(
                val, TABLE_TYPE))
        elif key == 'changes':
            for chv in self._parser.fetch_dicts_from_list(key, val, 'change'):
                self.changes.append(self._parser.parse_inner_change(
                    chv, self.__change_type))
        elif key == 'catalog' or key == 'catalogname':
            self.catalog_name = self.to_str(key, val).strip()
        elif key == 'schema' or key == 'schemaname':
            self.schema_name = self.to_str(key, val).strip()
        elif key == 'name' or key in self.__name_keys:
            self.name = self.to_str(key, val).strip()
        elif key == 'space' or key == 'tablespace':
            self.table_space = self.to_str(key, val).strip()
        elif key == 'constraints':
            for chv in self._parser.fetch_dicts_from_list(
                    key, val, 'constraint'):
                # this could be bad - name may not be parsed yet, but it doesn't
                # seem to be an issue.
                self.constraints.append(self._parser.parse_constraint(
                    self.name, chv))
        else:
            return False
        return True


class SqlStatementBuilder(object):
    def __init__(self, parent: BaseObjectBuilder):
        object.__init__(self)
        assert isinstance(parent, BaseObjectBuilder)
        self.__parent = parent
        self.syntax = 'native'
        self.platforms = []
        self.sql = None

    def set_platforms(self, key, platforms):
        if isinstance(platforms, str):
            self.platforms.extend([
                pla.strip() for pla in platforms.split(',')
            ])
        else:
            self.platforms.extend([
                self.__parent.to_str(key, pla).strip() for pla in platforms
            ])

    def make(self, src_dict):
        """
        :param src_dict: dict
        :return: SqlString
        """
        assert isinstance(src_dict, dict)

        for (key, val) in src_dict.items():
            key = _strip_key(key)

            # Don't use the BaseObjectBuilder to parse the keys.
            # if self.__parent.parse(key, val):
            #    continue

            if key == 'syntax':
                self.syntax = self.__parent.to_str(key, val).strip().lower()
            elif key == 'platforms':
                self.set_platforms(key, val)
            elif key == 'sql' or key == 'query':
                self.sql = self.__parent.to_str(key, val)
        if (self.sql is None or len(self.sql) <= 0 or
                not isinstance(self.sql, str)):
            self.__parent.problem(
                "expected 'sql' item (found " + repr(self.sql) + ")",
                ERROR_TYPE)
            self.sql = '<error in source>'
        # SqlString is not a BaseObject, so it cannot be "finished".
        return SqlString(self.sql, self.syntax, self.platforms)


class SchemaParser(object):
    """
    Note: not thread safe.
    """

    def __init__(self):
        object.__init__(self)
        self.__current_source = ""
        self.__source_order = {}
        self.__problems = None

    def strip_changes(self, source, stream):
        """
        Strip out the "changes" tags.

        :param source:
        :param stream:
        :return:
        """
        raise NotImplementedError()

    def parse(self, source: str, stream) -> list:
        """
        Parses the input stream, and returns a list of top-level Change
        instances and SchemaObject values.

        :param stream: Python stream type
        :rtype: list[Change or SchemaObject]
        """
        self.__problems = []
        self.__current_source = source
        try:
            obj_list = self._parse_stream(stream)
            ret = self.__problems
            for obj in obj_list:
                if obj is not None and obj not in ret:
                    ret.append(obj)
        finally:
            self.__current_source = ""
            self.__problems = None
        return ret

    def _parse_stream(self, stream) -> list:
        """
        :rtype: list[Change or SchemaObject]
        """
        raise NotImplementedError()

    @property
    def source(self) -> str:
        return self.__current_source

    def next_order(self, source=None):
        """
        Add the next item's implicit loading order.
        """
        if source is None:
            source = self.__current_source
        assert source is not None
        if source not in self.__source_order:
            self.__source_order[source] = [len(self.__source_order), [-1]]
        self.__source_order[source][1][-1] += 1
        ret = [
            self.__source_order[source][0],
            len(self.__source_order[source][1]) - 1,
            self.__source_order[source][1][-1]
        ]
        return ret

    def next_explicit_order(self, order, source=None):
        """
        Define the next item's loading order explicitly.
        """
        assert isinstance(order, int)
        if source is None:
            source = self.__current_source
        assert source is not None
        if source not in self.__source_order:
            self.__source_order[source] = [len(self.__source_order), [-1]]
        # make sure we have 1 more entry after the requested order.
        while len(self.__source_order[source][1] <= order):
            self.__source_order[source][1].append(-1)
        self.__source_order[source][order] += 1
        ret = []
        ret.extend(self.__source_order[source])
        return ret

    def _parse_dict(self, file_dict: dict) -> list:
        """
        Takes a dictionary of values, similar to a JSon object, and returns
        the parsed schema values.  Used only for the top-level dictionary.

        :param file_dict: dictionary with string keys, and values of lists,
            strings, numerics, nulls, or dictionaries.
        :rtype: list[Change or SchemaObject]
        """
        if not isinstance(file_dict, dict):
            self.problem("top level must be a dictionary", FATAL_TYPE)
            return None
        ret = []

        for (key, val) in file_dict.items():
            key = _strip_key(key)
            if key == 'changes':
                for chv in self.fetch_dicts_from_list(key, val, 'change'):
                    ret.append(self._parse_top_change(chv))
            elif key == 'change':
                ret.append(self._parse_top_change(val))
            elif key == 'tables':
                for chv in self.fetch_dicts_from_list(key, val, 'table'):
                    ret.append(self._parse_table(chv))
            elif key == 'table':
                ret.append(self._parse_table(val))
            elif key == 'views':
                for chv in self.fetch_dicts_from_list(key, val, 'view'):
                    ret.append(self._parse_view(chv))
            elif key == 'view':
                ret.append(self._parse_view(val))
            elif key == 'procedures':
                for chv in self.fetch_dicts_from_list(
                        key, val, 'procedure'):
                    ret.append(self._parse_procedure(chv))
            elif key == 'procedure':
                ret.append(self._parse_procedure(val))
            elif key == 'sequences':
                for chv in self.fetch_dicts_from_list(key, val, 'sequence'):
                    ret.append(self._parse_sequence(chv))
            elif key == 'sequence':
                ret.append(self._parse_sequence(val))
            else:
                self.problem("unknown key (" + key + ") set to " +
                             repr(val), WARNING_TYPE)
        return ret

    def _parse_top_change(self, top_change_dict: dict):
        """
        Parse a change that's outside a schema structure.
        """
        if not isinstance(top_change_dict, dict):
            self.problem("top change value is not a dictionary", FATAL_TYPE)
            return None

        change_obj = BaseObjectBuilder(self)
        sql_set = []
        schema_type = None
        change_type = SQL_CHANGE
        affects = []

        for (key, val) in top_change_dict.items():
            key = _strip_key(key)
            if change_obj.parse(key, val):
                # handled implicitly
                pass
            elif key == 'schema' or key == 'schematype':
                schema_type = change_obj.to_schema_type(key, val)
            elif key == 'change' or key == 'changetype':
                change_type = change_obj.to_change_type(key, val)
            elif key == 'affects':
                if isinstance(val, str):
                    affects = []
                    for val2 in val.split(','):
                        affects.append(val2.strip())
                elif isinstance(val, Iterable):
                    affects = []
                    for val2 in val:
                        affects.append(change_obj.to_str(key, val2.strip()))
                else:
                    change_obj.problem(
                        key + ": expected list or string, found " + repr(val),
                        ERROR_TYPE)
            elif key == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        key, val, ['dialect']):
                    sql = SqlStatementBuilder(change_obj)
                    sql_set.append(sql.make(chv))
            elif key in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(change_obj)
                sql_set.append(sql.make(chv))

            # Changes (e.g. upgrades) are not part of auto-generated code,
            # so there are no arguments.

            else:
                change_obj.problem(
                    "unknown key (" + key + ") set to " + repr(val),
                    WARNING_TYPE)

        if change_type != SQL_CHANGE:
            self.problem("only sql changes supported at top-level", FATAL_TYPE)
            return None
        if schema_type is None:
            self.problem("did not specify schema type for change", FATAL_TYPE)
            return None

        ret = SqlChange(change_obj.order, change_obj.comment, schema_type,
                        SqlSet(sql_set, None), affects)
        change_obj.finish(ret)
        return ret

    def _parse_table(self, table_dict):
        if not isinstance(table_dict, dict):
            self.problem('"table" must be a dictionary', FATAL_TYPE)
            return None

        table_obj = NameSpaceObjectBuilder(
            self, ['tablename'], TABLE_TYPE, False)
        columns = []
        wheres = []
        extended = []

        for (key, val) in table_dict.items():
            key = _strip_key(key)
            if table_obj.parse(key, val):
                # handled by parse
                pass
            elif key == 'column':
                columns.append(self._parse_column(val))
            elif key == 'columns':
                for chv in self.fetch_dicts_from_list(key, val, 'column'):
                    columns.append(self._parse_column(chv))
            elif key in ['wheres', 'whereclauses']:
                for chv in self.fetch_dicts_from_list(key, val, 'where'):
                    wheres.append(self._parse_where(chv, table_obj))
            elif key in ['extendedactions', 'extendedsql', 'extendsql',
                         'extend']:
                for chv in self.fetch_dicts_from_list(key, val, 'sql'):
                    extended.append(self._parse_extended_sql(chv, table_obj))
            else:
                table_obj.unknown_key(key, val)

        if table_obj.name is None or len(table_obj.name) <= 0:
            table_obj.problem("must set a table name", FATAL_TYPE)
            return None
        return table_obj.finish(Table(
            table_obj.order, table_obj.comment, table_obj.catalog_name,
            table_obj.schema_name, table_obj.name, table_obj.table_space,
            columns, table_obj.constraints, table_obj.changes, wheres,
            extended))

    def _parse_view(self, d):
        if not isinstance(d, dict):
            self.problem('"view" must be a dictionary', FATAL_TYPE)
            return None

        view_obj = NameSpaceObjectBuilder(self, ['viewname'], VIEW_TYPE, True)
        replace_if_exists = True
        sql_set = []
        columns = []
        wheres = []
        extended = []

        for (key, val) in d.items():
            key = _strip_key(key)
            if view_obj.parse(key, val):
                # handled by parse
                pass
            elif key == 'replace' or key == 'replaceifexists':
                replace_if_exists = view_obj.to_boolean(key, val)
            elif key == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        key, val, ['dialect']):
                    sql = SqlStatementBuilder(view_obj)
                    sql_set.append(sql.make(chv))
            elif key in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(view_obj)
                sql_set.append(sql.make(chv))
            elif key == 'column':
                columns.append(self._parse_column(val))
            elif key == 'columns':
                for chv in self.fetch_dicts_from_list(key, val, 'column'):
                    columns.append(self._parse_column(chv))
            elif key in ['wheres', 'whereclauses']:
                for chv in self.fetch_dicts_from_list(key, val, 'where'):
                    wheres.append(self._parse_where(chv, view_obj))
            elif key in ['extendedactions', 'extendedsql', 'extendsql',
                         'extend']:
                for chv in self.fetch_dicts_from_list(key, val, 'sql'):
                    extended.append(self._parse_extended_sql(chv, view_obj))

            # Views are not part of auto-generated code, so they do not have
            # arguments.

            else:
                view_obj.unknown_key(key, val)

        if len(sql_set) <= 0:
            view_obj.problem("no sql specified for view definition", FATAL_TYPE)
            return None
        return view_obj.finish(View(
            view_obj.order, view_obj.comment, view_obj.catalog_name,
            replace_if_exists, view_obj.schema_name, view_obj.name,
            SqlSet(sql_set, None), columns, view_obj.constraints,
            view_obj.changes, wheres, extended))

    def _parse_procedure(self, procedure_dict):
        """
        Parse a stored procedure.
        """
        raise NotImplementedError()

    def _parse_sequence(self, sequence_dict):
        """
        Parse a sequence.
        """
        raise NotImplementedError()

    def parse_inner_change(self, change_dict, schema_type):
        """
        Parse a change that's inside another structure.
        """
        assert isinstance(change_dict, dict)

        change_obj = BaseObjectBuilder(self)
        sql_set = []
        affects = []
        change_type = SQL_CHANGE
        previous_name = None

        for (key, val) in change_dict.items():
            key = _strip_key(key)
            if change_obj.parse(key, val):
                # handled
                pass
            elif key in ['schema', 'schematype']:
                schema_type = change_obj.to_schema_type(key, val)
            elif key in ['change', 'changetype', 'type']:
                change_type = change_obj.to_change_type(key, val)
            elif key in ['previously', 'fromname', 'was']:
                previous_name = change_obj.to_str(key, val).strip()
            elif key == 'affects':
                if isinstance(val, list) or isinstance(val, tuple):
                    affects = []
                    for val2 in val:
                        affects.append(change_obj.to_str(key, val2).strip())
                elif isinstance(val, str):
                    affects = []
                    for val2 in val.split(','):
                        affects.append(val2.strip())
                else:
                    change_obj.problem(
                        key + ': must be a string or list, found ' + repr(val),
                        ERROR_TYPE)
            elif key == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        key, val, ['dialect']):
                    sql = SqlStatementBuilder(change_obj)
                    sql_set.append(sql.make(chv))
            elif key in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(change_obj)
                sql_set.append(sql.make(chv))

            # Changes are not part of auto-generated code, and so do not have
            # arguments.

            else:
                change_obj.unknown_key(key, val)

        if change_type == SQL_CHANGE:
            if len(sql_set) <= 0:
                change_obj.problem(
                    "requires 'sql' or 'dialects' key for sql change",
                    FATAL_TYPE)
                return None
            return SqlChange(change_obj.order, change_obj.comment, schema_type,
                             SqlSet(sql_set, None), affects)
        else:
            return SchemaChange(change_obj.order, change_obj.comment,
                                schema_type, change_type, previous_name,
                                affects)

    def _parse_column(self, column_dict):
        """
        Parse a column, either from a view or table or stored procedure.
        """
        assert isinstance(column_dict, dict)

        column_obj = BaseObjectBuilder(self)
        name = None
        value_type = None
        data_type = None
        value = None
        default_value = None
        auto_increment = False
        remarks = None
        before_column = None
        after_column = None
        position = None
        constraints = []
        changes = []

        for (key, val) in column_dict.items():
            key = _strip_key(key)
            if column_obj.parse(key, val):
                # Handled
                pass
            elif key == 'change':
                changes.append(self.parse_inner_change(val, COLUMN_TYPE))
            elif key == 'changes':
                for chv in self.fetch_dicts_from_list(key, val, 'change'):
                    changes.append(self.parse_inner_change(chv, COLUMN_TYPE))
            elif key == 'name':
                name = column_obj.to_str(key, val).strip()
            elif key == 'type':
                value_type = column_obj.to_str(key, val).strip()
            elif key == 'datatype':
                data_type = column_obj.to_str(key, val).strip()
            elif key == 'value':
                value = self._parse_value_type_value(val, column_obj)
            elif key == 'default' or key == 'defaultvalue':
                default_value = self._parse_value_type_value(val, column_obj)
            elif key == 'remarks':
                remarks = column_obj.to_str(key, val)
            elif key == 'before' or key == 'beforecolumn':
                before_column = column_obj.to_str(key, val).strip()
            elif key == 'after' or key == 'aftercolumn':
                after_column = column_obj.to_str(key, val).strip()
            elif key == 'autoincrement':
                auto_increment = column_obj.to_boolean(key, val)
            elif key == 'position':
                position = column_obj.to_int(key, val)
                assert position >= 0
            elif key == 'constraints':
                for chv in self.fetch_dicts_from_list(key, val, 'constraint'):
                    constraints.append(self.parse_constraint(name, chv))
            else:
                column_obj.unknown_key(key, val)

        if name is None or len(name) <= 0:
            column_obj.problem("no name set for column", FATAL_TYPE)
            return None
        if value_type is None or len(value_type) <= 0:
            column_obj.problem("no value type set for column", FATAL_TYPE)
            return None
        if data_type is None:
            data_type = value_type
        elif len(data_type) <= 0:
            column_obj.problem("data type set to empty value", FATAL_TYPE)
            return None
        return column_obj.finish(Column(
            column_obj.order, column_obj.comment, name, value_type,
            data_type, value, default_value, auto_increment, remarks,
            before_column, after_column, position, constraints,
            changes))

    def _parse_where(self, where_dict: dict, parent: BaseObjectBuilder):
        """
        Parse a where clause, which is used for generated code.
        """
        assert isinstance(where_dict, dict)
        assert isinstance(parent, BaseObjectBuilder)

        name = None
        sql_sets = []
        arguments = []

        for (key, val) in where_dict.items():
            key = _strip_key(key)
            if key == 'dialects':
                for chv in self.fetch_dicts_from_list(key, val, 'dialect'):
                    sql = SqlStatementBuilder(parent)
                    sql_sets.append(sql.make(chv))
            elif key in ['sql', 'value']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(parent)
                sql_sets.append(sql.make(chv))
            elif key == 'name':
                name = parent.to_str(key, val).strip()
            elif key in ['arg', 'argument']:
                arguments.append(self._parse_argument(val, parent))
            elif key in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        key, val, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv, parent))
            else:
                parent.unknown_key(key, val)
        if len(sql_sets) <= 0:
            parent.problem("no sql or dialects set for where clause",
                           FATAL_TYPE)
            return None

        return WhereClause(name, SqlSet(sql_sets, arguments))

    def _parse_extended_sql(self, ext_sql_dict: dict,
                            parent: BaseObjectBuilder):
        """
        Parse extended SQL referenced from code, so is used in generated code.
        """

        assert isinstance(ext_sql_dict, dict)
        assert isinstance(parent, BaseObjectBuilder)

        name = None
        sql_sets = []
        post_sql_sets = []
        sql_type = None
        arguments = []

        for (key, val) in ext_sql_dict.items():
            if key in ['schematype', 'type', 'operation']:
                sql_type = parent.to_str(key, val).strip()
            elif key in ['dialects', 'pre_dialects', 'pre']:
                for chv in self.fetch_dicts_from_list(
                        key, val, ['dialect']):
                    sql = SqlStatementBuilder(parent)
                    sql_sets.append(sql.make(chv))
            elif key in ['post_dialects', 'post']:
                for chv in self.fetch_dicts_from_list(
                        key, val, ['dialect']):
                    sql = SqlStatementBuilder(parent)
                    post_sql_sets.append(sql.make(chv))
            elif key in ['statement', 'sql', 'query', 'execute', 'pre_sql']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(parent)
                sql_sets.append(sql.make(chv))
            elif key in ['post_sql']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(parent)
                post_sql_sets.append(sql.make(chv))
            elif key == 'name':
                name = parent.to_str(key, val).strip()
            elif key in ['arg', 'argument']:
                arguments.append(self._parse_argument(val, parent))
            elif key in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        key, val, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv, parent))
            # TODO add support for columns if type is 'query'
            else:
                parent.unknown_key(key, val)

        if len(sql_sets) <= 0:
            parent.problem("no sql or dialects set for extended sql",
                           FATAL_TYPE)
            return None

        post = None
        if len(post_sql_sets) > 0:
            post = SqlSet(post_sql_sets, arguments)

        return ExtendedSql(name, sql_type, SqlSet(sql_sets, arguments), post)

    def _parse_argument(self, arg_dict,
                        parent: BaseObjectBuilder):
        """
        Parse a SQL argument.
        """
        assert isinstance(arg_dict, dict)
        assert isinstance(parent, BaseObjectBuilder)

        name = None
        arg_type = None
        is_collection = False

        for (key, val) in arg_dict.items():
            key = _strip_key(key)
            if key == 'name':
                name = parent.to_str(key, val).strip()
            elif key == 'type':
                arg_type = parent.to_str(key, val).strip()
            else:
                parent.unknown_key(key, val)
        if name is None or len(name) <= 0:
            parent.problem('no name given to argument', FATAL_TYPE)
            return None
        if not isinstance(arg_type, str) or len(arg_type) <= 0:
            parent.problem('no type given to argument', FATAL_TYPE)
            return None
        if arg_type.startswith("set "):
            is_collection = True
            arg_type = arg_type[4:].strip()
            if len(arg_type) <= 0:
                parent.problem('no type given for setter argument', FATAL_TYPE)
                return None
        return SqlArgument(name, arg_type, is_collection)

    def parse_constraint(self, parent_column, constraint_dict):
        """
        Parse a generic constraint, which can be either code or SQL.
        """

        assert isinstance(constraint_dict, dict)

        cons_obj = BaseObjectBuilder(self)
        constraint_type = None
        changes = []
        sql_sets = []
        language = None
        code = None
        name = None
        column_names = []
        details = {}
        arguments = []

        for (key, val) in constraint_dict.items():
            key = _strip_key(key)
            if cons_obj.parse(key, val):
                # Handled
                pass
            elif key == 'change':
                changes.append(self.parse_inner_change(val, CONSTRAINT_TYPE))
            elif key == 'changes':
                for chv in self.fetch_dicts_from_list(key, val, 'change'):
                    changes.append(self.parse_inner_change(
                        chv, CONSTRAINT_TYPE))
            elif key == 'columns':
                if isinstance(val, str):
                    column_names.extend([chv.strip() for chv in val.split(',')])
                elif isinstance(val, list) or isinstance(val, tuple):
                    d_list = []
                    for chv in val:
                        if isinstance(chv, str):
                            column_names.append([chv.strip()])
                        elif isinstance(chv, dict):
                            d_list.append(chv)
                        else:
                            cons_obj.problem(
                                "columns can be a string, or contain a list of "
                                "strings or dictionaries", ERROR_TYPE)
                    for chv in self.fetch_dicts_from_list(
                            key, d_list, 'column'):
                        column_names.append(chv.strip())
            elif key == 'type':
                constraint_type = cons_obj.to_str(key, val).strip()
            elif key == 'dialects':
                for chv in self.fetch_dicts_from_list(key, val, 'dialect'):
                    sql = SqlStatementBuilder(cons_obj)
                    sql_sets.append(sql.make(chv))
            elif key == 'sql' or key == 'value':
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(cons_obj)
                sql_sets.append(sql.make(chv))
            elif key == 'language':
                language = cons_obj.to_str(key, val).strip().lower()
            elif key == 'code':
                code = cons_obj.to_str(key, val)
            elif key == 'name':
                name = cons_obj.to_str(key, val).strip()
            elif key in ['arg', 'argument']:
                arguments.append(self._parse_argument(val, cons_obj))
            elif key in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        key, val, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv, cons_obj))
            else:
                # Custom constraint key/values
                details[key] = val

        if len(column_names) <= 0 and parent_column is not None:
            column_names = [parent_column]

        if constraint_type is None or len(constraint_type) <= 0:
            self.problem('no constraint type given', FATAL_TYPE)
            return None
        if len(sql_sets) > 0:
            if language is not None:
                self.problem(
                    'a constraint must be either sql or language, not both',
                    FATAL_TYPE)
                return None
            if code is not None:
                self.problem(
                    'a constraint must be either sql or language, not both',
                    FATAL_TYPE)
                return None
            if name is not None:
                details['name'] = name
            return SqlConstraint(cons_obj.order, cons_obj.comment,
                                 constraint_type, column_names, details,
                                 SqlSet(sql_sets, arguments), changes)

        if language is not None and code is not None:
            if name is not None:
                details['name'] = name
            code_set = LanguageSet({language: code}, arguments)
            return LanguageConstraint(cons_obj.order, cons_obj.comment,
                                      constraint_type, column_names, details,
                                      code_set, changes)

        if name is not None:
            return NamedConstraint(cons_obj.order, cons_obj.comment,
                                   constraint_type, column_names, details, name,
                                   changes)

        return Constraint(cons_obj.order, cons_obj.comment, constraint_type,
                          column_names, details, changes)

    def problem(self, message, level: SchemaObjectType,
                source_line: int or None=None, source_col: int or None=None):
        problem = ErrorObject(
            self.__current_source, message, self.__current_source,
            source_line=source_line, source_col=source_col, level=level)
        self.__problems.append(problem)
        return problem

    def _parse_value_type_value(self, vtv_dict, parent: BaseObjectBuilder):
        """
        Parse a ValueTypeValue, which can either be for generated code to
        define what is inserted, or for default values.
        """

        assert isinstance(parent, BaseObjectBuilder)

        if vtv_dict is None or isinstance(vtv_dict, str):
            return ValueTypeValue(vtv_dict, None, None, None, None)
        if not isinstance(vtv_dict, dict):
            parent.problem('expected dictionary or string value, found ' +
                           repr(vtv_dict), FATAL_TYPE)
            return None

        sql_set = []
        arguments = []
        val_type = None
        val = None

        for (key, v) in vtv_dict.items():
            key = _strip_key(key)
            # if value_obj.parse(key, v):
            #    # Handled in the call
            #    pass
            if key == 'type':
                val_type = parent.to_str(key, v).strip()
            elif key == 'value':
                # NOTE: do not convert!
                val = v
            elif key == 'dialects':
                for chv in self.fetch_dicts_from_list(key, v, 'dialect'):
                    sql = SqlStatementBuilder(parent)
                    sql_set.append(sql.make(chv))
            elif key == 'sql':
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder(parent)
                sql_set.append(sql.make(chv))
            elif key in ['arg', 'argument']:
                arguments.append(self._parse_argument(v, parent))
            elif key in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        key, v, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv, parent))
            else:
                parent.unknown_key(key, v)

        if (val_type == 'int' or val_type == 'float' or val_type == 'double' or
                (val_type is not None and val_type.startswith('numeric'))):
            if len(arguments) > 0 or len(sql_set) > 0:
                self.problem(
                    'cannot specify constant value with arguments or sql',
                    FATAL_TYPE)
                return None
            # Cannot finish the value_obj, because this is not a BaseObject
            return ValueTypeValue(None, val, None, None, None)
        elif val_type == 'bool' or val_type == 'boolean':
            if len(arguments) > 0 or len(sql_set) > 0:
                self.problem(
                    'cannot specify constant value with arguments or sql',
                    FATAL_TYPE)
                return None
            # Cannot finish the value_obj, because this is not a BaseObject
            return ValueTypeValue(None, None, parent.to_boolean('type', val),
                                  None, None)
        elif val_type == 'date' or val_type == 'time' or val_type == 'datetime':
            if len(arguments) > 0 or len(sql_set) > 0:
                self.problem(
                    'cannot specify constant value with arguments or sql',
                    FATAL_TYPE)
                return None
            return ValueTypeValue(None, None, None, str(val), None)
        elif val_type == 'computed' or val_type == 'sql':
            if len(sql_set) < 0 and val is not None and len(val) > 0:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder(parent)
                sql_set.append(sql.make(chv))
            if len(sql_set) <= 0:
                self.problem(
                    "computed value types must have a value or dialect",
                    FATAL_TYPE)
                return None
            return ValueTypeValue(None, None, None, None,
                                  SqlSet(sql_set, arguments))
        elif (val_type == 'str' or val_type == 'string' or
                val_type == 'char' or val_type == 'varchar'):
            if len(arguments) > 0 or len(sql_set) > 0:
                self.problem(
                    'cannot specify constant value with arguments or sql',
                    FATAL_TYPE)
                return None
            return ValueTypeValue(str(val), None, None, None, None)
        else:
            self.problem("unknown value type " + val_type, FATAL_TYPE)
            return None

    def fetch_dicts_from_list(self, k, v, expected_elements):
        if not (isinstance(v, tuple) or isinstance(v, list)):
            self.problem('"' + k + '" does not contain a list, but ' + repr(v),
                         FATAL_TYPE)
            return []
        if isinstance(expected_elements, str):
            expected_elements = [expected_elements]
        ret = []
        for ch in v:
            for (kk, vv) in ch.items():
                kk = _strip_key(kk)
                if kk in expected_elements:
                    ret.append(vv)
                else:
                    self.problem(
                        'only ' + str(expected_elements) +
                        ' are allowed inside "' + k + '" (found "' +
                        repr(kk) + '")', FATAL_TYPE)
        return ret


def _strip_key(key):
    assert isinstance(key, str)
    for c in ' \r\n\t_-':
        key = key.replace(c, '')
    return key.lower()
