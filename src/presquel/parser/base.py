
from ..model.change import (SchemaChange, SqlChange, CHANGE_TYPES, SQL_CHANGE)
from ..model.base import (SCHEMA_OBJECT_TYPES,
                     TABLE_TYPE, VIEW_TYPE, CONSTRAINT_TYPE, COLUMN_TYPE,
                     SqlString, SqlArgument)
from ..model.schema import (Table, View,
                     Column, SqlConstraint, LanguageConstraint, Constraint,
                     NamedConstraint, WhereClause, ExtendedSql,
                     ValueTypeValue, SqlSet, LanguageSet)


class BaseObjectBuilder(object):
    def __init__(self, parser):
        assert isinstance(parser, SchemaParser)
        object.__init__(self)
        self._parser = parser
        self.order = parser.next_order()
        self.comment = None

    def parse(self, k, v):
        if k == 'error':
            self._parser.error('explicit error "' + str(v) + '"')
        elif k == 'warning':
            print("**WARNING** (" + str(self._parser.source) + ")", str(v))
        elif k == 'note':
            print("Note (" + str(self._parser.source) + ")", str(v))
        elif k == 'comment':
            self.comment = v.strip()
        elif k == 'order':
            self.order = self._parser.next_explicit_order(int(v))
        else:
            return False
        return True

    def _fail_on(self, k, v):
        """
        Create a failure error.
        """
        self._parser.error('unknown key (' + str(k) + ') set to ' + repr(v))


class NameSpaceObjectBuilder(BaseObjectBuilder):
    def __init__(self, parser, name_keys, change_type, is_readonly):
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

    def parse(self, k, v):
        if BaseObjectBuilder.parse(self, k, v):
            return True
        if k == 'change':
            self.changes.append(self._parser.parse_inner_change(v, TABLE_TYPE))
        elif k == 'changes':
            for chv in self._parser.fetch_dicts_from_list(k, v, 'change'):
                self.changes.append(self._parser.parse_inner_change(
                    chv, self.__change_type))
        elif k == 'catalog' or k == 'catalogname':
            self.catalog_name = str(v).strip()
        elif k == 'schema' or k == 'schemaname':
            self.schema_name = str(v).strip()
        elif k == 'name' or k in self.__name_keys:
            self.name = str(v).strip()
        elif k == 'space' or k == 'tablespace':
            self.table_space = str(v).strip()
        elif k == 'constraints':
            for chv in self._parser.fetch_dicts_from_list(k, v, 'constraint'):
                # this could be bad - name may not be parsed yet, but it doesn't
                # seem to be an issue.
                self.constraints.append(self._parser.parse_constraint(
                    self.name, chv))
        else:
            return False
        return True


class SqlStatementBuilder(object):
    def __init__(self):
        object.__init__(self)
        self.syntax = 'native'
        self.platforms = []
        self.sql = None

    def set_platforms(self, platforms):
        if isinstance(platforms, str):
            self.platforms.extend([
                s.strip() for s in platforms.split(',')
            ])
        else:
            self.platforms.extend([
                p.strip() for p in platforms
            ])

    def make(self, src_dict):
        """
        :param src_dict: dict
        :return: SqlString
        """
        assert isinstance(src_dict, dict)

        for (k, v) in src_dict.items():
            k = _strip_key(k)
            if k == 'syntax':
                self.syntax = v.strip().lower()
            elif k == 'platforms':
                self.set_platforms(v)
            elif k == 'sql' or k == 'query':
                if isinstance(v, int) or isinstance(v, float):
                    v = str(v)
                assert isinstance(v, str)
                self.sql = v
        if (self.sql is None or len(self.sql) <= 0 or
                not isinstance(self.sql, str)):
            raise Exception("expected 'sql' item (found " + repr(self.sql) +
                            ")")
        return SqlString(self.sql, self.syntax, self.platforms)


class SchemaParser(object):
    """
    Note: not thread safe.
    """

    def __init__(self):
        object.__init__(self)
        self.__current_source = None
        self.__source_order = {}

    def strip_changes(self, source, stream):
        """
        Strip out the "changes" tags.

        :param source:
        :param stream:
        :return:
        """
        raise NotImplementedError()

    def parse(self, source, stream):
        """
        Parses the input stream, and returns a list of top-level Change
        instances and SchemaObject values.

        :param stream: Python stream type
        :return: tuple(SchemaVersion)
        """
        raise NotImplementedError()

    @property
    def source(self):
        return self.__current_source

    def next_order(self, source = None):
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

    def next_explicit_order(self, order, source = None):
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

    def _parse_dict(self, source, file_dict):
        """
        Takes a dictionary of values, similar to a JSon object, and returns
        the parsed schema values.  Used only for the top-level dictionary.

        :param file_dict: dictionary with string keys, and values of lists, strings,
            numerics, nulls, or dictionaries.
        :return:
        """
        self.__current_source = source
        try:
            if not isinstance(file_dict, dict):
                self.error("top level must be a dictionary")
            ret = []

            for (k, v) in file_dict.items():
                k = _strip_key(k)
                if k == 'changes':
                    for chv in self.fetch_dicts_from_list(k, v, 'change'):
                        ret.append(self._parse_top_change(chv))
                elif k == 'change':
                    ret.append(self._parse_top_change(v))
                elif k == 'tables':
                    for chv in self.fetch_dicts_from_list(k, v, 'table'):
                        ret.append(self._parse_table(chv))
                elif k == 'table':
                    ret.append(self._parse_table(v))
                elif k == 'views':
                    for chv in self.fetch_dicts_from_list(k, v, 'view'):
                        ret.append(self._parse_view(chv))
                elif k == 'view':
                    ret.append(self._parse_view(v))
                elif k == 'procedures':
                    for chv in self.fetch_dicts_from_list(k, v, 'procedure'):
                        ret.append(self._parse_procedure(chv))
                elif k == 'procedure':
                    ret.append(self._parse_procedure(v))
                elif k == 'sequences':
                    for chv in self.fetch_dicts_from_list(k, v, 'sequence'):
                        ret.append(self._parse_sequence(chv))
                elif k == 'sequence':
                    ret.append(self._parse_sequence(v))
                else:
                    self.error("unknown key (" + k + ") set to " + repr(v))
        finally:
            self.__current_source = None
        return ret

    def _parse_top_change(self, top_change_dict):
        """
        Parse a change that's outside a schema structure.
        """
        if not isinstance(top_change_dict, dict):
            self.error("top change value is not a dictionary")

        change_obj = BaseObjectBuilder(self)
        sql_set = []
        schema_type = None
        change_type = SQL_CHANGE

        for (k, v) in top_change_dict.items():
            k = _strip_key(k)
            if change_obj.parse(k, v):
                # handled implicitly
                pass
            elif k == 'schema' or k == 'schematype':
                schema_type = _parse_schema_type(v)
            elif k == 'change' or k == 'changetype':
                change_type = _parse_change_type(v)
            elif k == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(chv))
            elif k in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(chv))

            # Changes (e.g. upgrades) are not part of auto-generated code,
            # so there are no arguments.

            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if change_type != SQL_CHANGE:
            self.error("only sql changes supported at top-level")
        if schema_type is None:
            self.error("did not specify schema type for change")

        return SqlChange(change_obj.order, change_obj.comment, schema_type,
                         SqlSet(sql_set, None))

    def _parse_table(self, table_dict):
        if not isinstance(table_dict, dict):
            self.error('"table" must be a dictionary')

        table_obj = NameSpaceObjectBuilder(self, ['tablename'], TABLE_TYPE,
                                           False)
        columns = []
        wheres = []
        extended = []

        for (k, v) in table_dict.items():
            k = _strip_key(k)
            if table_obj.parse(k, v):
                # handled by parse
                pass
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                for chv in self.fetch_dicts_from_list(k, v, 'column'):
                    columns.append(self._parse_column(chv))
            elif k in ['wheres', 'whereclauses']:
                for chv in self.fetch_dicts_from_list(k, v, 'where'):
                    wheres.append(self._parse_where(chv))
            elif k in ['extendedactions', 'extendedsql', 'extendsql', 'extend']:
                for chv in self.fetch_dicts_from_list(k, v, 'sql'):
                    extended.append(self._parse_extended_sql(chv))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        assert table_obj.name is not None and len(table_obj.name) > 0
        return Table(table_obj.order, table_obj.comment,
                     table_obj.catalog_name, table_obj.schema_name,
                     table_obj.name, table_obj.table_space, columns,
                     table_obj.constraints, table_obj.changes,
                     wheres, extended)

    def _parse_view(self, d):
        assert isinstance(d, dict)

        view_obj = NameSpaceObjectBuilder(self, ['viewname'], VIEW_TYPE, True)
        replace_if_exists = True
        sql_set = []
        columns = []
        wheres = []
        extended = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if view_obj.parse(k, v):
                # handled by parse
                pass
            elif k == 'replace' or k == 'replaceifexists':
                replace_if_exists = _parse_boolean(v)
            elif k == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(chv))
            elif k in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(chv))
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                for chv in self.fetch_dicts_from_list(k, v, 'column'):
                    columns.append(self._parse_column(chv))
            elif k in ['wheres', 'whereclauses']:
                for chv in self.fetch_dicts_from_list(k, v, 'where'):
                    wheres.append(self._parse_where(chv))
            elif k in ['extendedactions', 'extendedsql', 'extendsql', 'extend']:
                for chv in self.fetch_dicts_from_list(k, v, 'sql'):
                    extended.append(self._parse_extended_sql(chv))

            # Views are not part of auto-generated code, so they do not have
            # arguments.

            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        assert len(sql_set) > 0
        return View(view_obj.order, view_obj.comment, view_obj.catalog_name,
                    replace_if_exists, view_obj.schema_name, view_obj.name,
                    SqlSet(sql_set, None), columns, view_obj.constraints,
                    view_obj.changes, wheres, extended)

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

        for (k, v) in change_dict.items():
            k = _strip_key(k)
            if change_obj.parse(k, v):
                # handled
                pass
            elif k in ['schema', 'schematype']:
                schema_type = _parse_schema_type(v)
            elif k in ['change', 'changetype', 'type']:
                change_type = _parse_change_type(v)
            elif k in ['previously', 'fromname', 'was']:
                previous_name = v.strip()
            elif k == 'affects':
                if isinstance(v, list) or isinstance(v, tuple):
                    affects = []
                    for val in v:
                        affects.append(val.strip())
                elif isinstance(v, str):
                    affects = []
                    vals = v.split(',')
                    for val in vals:
                        affects.append(val.strip())
            elif k == 'dialects':
                for chv in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(chv))
            elif k in ['statement', 'sql', 'query', 'execute']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(chv))

            # Changes are not part of auto-generated code, and so do not have
            # arguments.

            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if change_type == SQL_CHANGE:
            if len(sql_set) <= 0:
                return self.error("requires 'sql' or 'dialects' for sql change")
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

        for (k, v) in column_dict.items():
            k = _strip_key(k)
            if column_obj.parse(k, v):
                # Handled
                pass
            elif k == 'change':
                changes.append(self.parse_inner_change(v, COLUMN_TYPE))
            elif k == 'changes':
                for chv in self.fetch_dicts_from_list(k, v, 'change'):
                    changes.append(self.parse_inner_change(chv, COLUMN_TYPE))
            elif k == 'name':
                name = str(v).strip()
            elif k == 'type':
                value_type = str(v).strip()
            elif k == 'datatype':
                data_type = str(v).strip()
            elif k == 'value':
                value = self._parse_value_type_value(v)
            elif k == 'default' or k == 'defaultvalue':
                default_value = self._parse_value_type_value(v)
            elif k == 'remarks':
                remarks = str(v)
            elif k == 'before' or k == 'beforecolumn':
                before_column = str(v).strip()
            elif k == 'after' or k == 'aftercolumn':
                after_column = str(v).strip()
            elif k == 'autoincrement':
                auto_increment = _parse_boolean(v)
            elif k == 'position':
                position = int(v)
                assert position >= 0
            elif k == 'constraints':
                for chv in self.fetch_dicts_from_list(k, v, 'constraint'):
                    constraints.append(self.parse_constraint(name, chv))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        assert name is not None and len(name) > 0
        assert value_type is not None and len(value_type) > 0
        if data_type is None:
            data_type = value_type
        else:
            assert len(data_type) > 0
        return Column(column_obj.order, column_obj.comment, name, value_type,
                      data_type, value, default_value, auto_increment, remarks,
                      before_column, after_column, position, constraints,
                      changes)

    def _parse_where(self, where_dict):
        """
        Parse a where clause, which is used for generated code.
        """
        assert isinstance(where_dict, dict)

        name = None
        sql_sets = []
        arguments = []

        for  (k, v) in where_dict.items():
            k = _strip_key(k)
            if k == 'dialects':
                for chv in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(chv))
            elif k in ['sql', 'value']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(chv))
            elif k == 'name':
                name = v.strip()
            elif k in ['arg', 'argument']:
                arguments.append(self._parse_argument(v))
            elif k in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))
        if len(sql_sets) <= 0:
            self.error("no sql or dialects set for where clause")

        return WhereClause(name, SqlSet(sql_sets, arguments))

    def _parse_extended_sql(self, ext_sql_dict):
        """
        Parse extended SQL referenced from code, so is used in generated code.
        """

        assert isinstance(ext_sql_dict, dict)

        name = None
        sql_sets = []
        post_sql_sets = []
        sql_type = None
        arguments = []

        for (k, v) in ext_sql_dict.items():
            if k in ['schematype', 'type', 'operation']:
                assert isinstance(v, str)
                sql_type = v.strip()
            elif k in ['dialects', 'pre_dialects', 'pre']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(chv))
            elif k in ['post_dialects', 'post']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    post_sql_sets.append(sql.make(chv))
            elif k in ['statement', 'sql', 'query', 'execute', 'pre_sql']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(chv))
            elif k in ['post_sql']:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    sql: v
                }
                sql = SqlStatementBuilder()
                post_sql_sets.append(sql.make(chv))
            elif k == 'name':
                name = v.strip()
            elif k in ['arg', 'argument']:
                arguments.append(self._parse_argument(v))
            elif k in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv))
            # TODO add support for columns if type is 'query'
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if len(sql_sets) <= 0:
            self.error("no sql or dialects set for extended sql")

        post = None
        if len(post_sql_sets) > 0:
            post = SqlSet(post_sql_sets, arguments)

        return ExtendedSql(name, sql_type, SqlSet(sql_sets, arguments), post)

    def _parse_argument(self, arg_dict):
        """
        Parse a SQL argument.
        """
        assert isinstance(arg_dict, dict)

        name = None
        arg_type = None
        is_collection = False

        for (k, v) in arg_dict.items():
            k = _strip_key(k)
            if k == 'name':
                assert isinstance(v, str)
                assert name is None
                name = v.strip()
                assert len(name) > 0
            elif k == 'type':
                assert isinstance(v, str)
                assert arg_type is None
                arg_type = v.strip()
                assert len(arg_type) > 0
        assert name is not None
        assert arg_type is not None
        assert isinstance(arg_type, str)
        if arg_type.startswith("set "):
            is_collection = True
            arg_type = arg_type[4:].strip()
            assert len(arg_type) > 0
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

        for (k, v) in constraint_dict.items():
            k = _strip_key(k)
            if cons_obj.parse(k, v):
                # Handled
                pass
            elif k == 'change':
                changes.append(self.parse_inner_change(v, CONSTRAINT_TYPE))
            elif k == 'changes':
                for chv in self.fetch_dicts_from_list(k, v, 'change'):
                    changes.append(self.parse_inner_change(
                        chv, CONSTRAINT_TYPE))
            elif k == 'columns':
                if isinstance(v, str):
                    column_names.extend([chv.strip() for chv in v.split(',')])
                elif isinstance(v, list) or isinstance(v, tuple):
                    d_list = []
                    for chv in v:
                        if isinstance(chv, str):
                            column_names.append([chv.strip()])
                        elif isinstance(chv, dict):
                            d_list.append(chv)
                        else:
                            raise Exception("columns can be a string, or "
                                            "contain a list of strings or "
                                            "dictionaries")
                    for chv in self.fetch_dicts_from_list(k, d_list, 'column'):
                        column_names.append(chv.strip())
            elif k == 'type':
                constraint_type = str(v).strip()
            elif k == 'dialects':
                for chv in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(chv))
            elif k == 'sql' or k == 'value':
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(chv))
            elif k == 'language':
                language = v.strip().lower()
            elif k == 'code':
                code = v
            elif k == 'name':
                name = v.strip()
            elif k in ['arg', 'argument']:
                arguments.append(self._parse_argument(v))
            elif k in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv))
            else:
                # Custom constraint key/values
                details[k] = v

        if len(column_names) <= 0 and parent_column is not None:
            column_names = [parent_column]

        assert constraint_type is not None and len(constraint_type) > 0
        if len(sql_sets) > 0:
            assert language is None
            assert code is None
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

    def error(self, message):
        """
        Raise an error that includes the source of the problem.
        """
        raise Exception(str(self.__current_source) + ': ' + str(message))

    def _parse_value_type_value(self, vtv_dict):
        """
        Parse a ValueTypeValue, which can either be for generated code to
        define what is inserted, or for default values.


        """

        if vtv_dict is None or isinstance(vtv_dict, str):
            return ValueTypeValue(vtv_dict, None, None, None, None)

        assert isinstance(vtv_dict, dict)

        value_obj = BaseObjectBuilder(self)
        sql_set = []
        arguments = []
        val_type = None
        val = None

        for (k, v) in vtv_dict.items():
            k = _strip_key(k)
            if value_obj.parse(k, v):
                # Handled in the call
                pass
            if k == 'type':
                val_type = str(v).strip()
            elif k == 'value':
                val = v
            elif k == 'dialects':
                for chv in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(chv))
            elif k == 'sql':
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(chv))
            elif k in ['arg', 'argument']:
                arguments.append(self._parse_argument(v))
            elif k in ['arguments', 'args']:
                for chv in self.fetch_dicts_from_list(
                        k, v, ['arg', 'argument']):
                    arguments.append(self._parse_argument(chv))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if (val_type == 'int' or val_type == 'float' or val_type == 'double' or
                (val_type is not None and val_type.startswith('numeric'))):
            assert len(arguments) <= 0 and len(sql_set) <= 0
            return ValueTypeValue(None, val, None, None, None)
        elif val_type == 'bool' or val_type == 'boolean':
            assert len(arguments) <= 0 and len(sql_set) <= 0
            return ValueTypeValue(None, None, _parse_boolean(val), None, None)
        elif val_type == 'date' or val_type == 'time' or val_type == 'datetime':
            assert len(arguments) <= 0 and len(sql_set) <= 0
            return ValueTypeValue(None, None, None, str(val), None)
        elif val_type == 'computed' or val_type == 'sql':
            if len(sql_set) < 0 and val is not None and len(val) > 0:
                chv = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(chv))
            if len(sql_set) <= 0:
                self.error("computed value types must have a value or dialect")
            return ValueTypeValue(None, None, None, None,
                SqlSet(sql_set, arguments))
        elif (val_type == 'str' or val_type == 'string' or
                val_type == 'char' or val_type == 'varchar'):
            assert len(arguments) <= 0 and len(sql_set) <= 0
            return ValueTypeValue(str(val), None, None, None, None)
        else:
            self.error("unknown value type " + val_type)

    def fetch_dicts_from_list(self, k, v, expected_elements):
        assert isinstance(v, tuple) or isinstance(v, list)
        if not (isinstance(v, tuple) or isinstance(v, list)):
            self.error('"' + k + '" does not contain a list, but ' + repr(v))
        if isinstance(expected_elements, str):
            expected_elements = [expected_elements]
        ret = []
        for ch in v:
            for (kk, vv) in ch.items():
                kk = _strip_key(kk)
                if kk in expected_elements:
                    ret.append(vv)
                else:
                    self.error('only ' + str(expected_elements) +
                               ' are allowed inside "' + k + '" (found "' +
                               str(kk) + '")')
        return ret


def _parse_schema_type(type_name):
    type_name = type_name.strip().lower()
    for t in SCHEMA_OBJECT_TYPES:
        if t.name == type_name:
            return t
    raise Exception("unknown schema object type: " + type_name)


def _parse_change_type(type_name):
    type_name = type_name.strip().lower()
    for t in CHANGE_TYPES:
        if t.name == type_name:
            return t
    raise Exception("unknown change type: " + type_name)


def _parse_boolean(v):
    if v is True or v is False:
        return v
    v = str(v).strip().lower()
    return v == "1" or v == "true" or v == "on" or v == "yes"


def _strip_key(key):
    assert isinstance(key, str)
    for c in ' \r\n\t_-':
        key = key.replace(c, '')
    return key.lower()
