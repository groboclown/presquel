
from ..model import (SCHEMA_OBJECT_TYPES, CHANGE_TYPES,
                     SQL_CHANGE, SqlChange, Change,
                     TABLE_TYPE, Table,
                     VIEW_TYPE, View, CONSTRAINT_TYPE, COLUMN_TYPE,
                     Column, SqlConstraint, LanguageConstraint, Constraint,
                     NamedConstraint, WhereClause, ExtendedSql,
                     ValueTypeValue, SqlString, SqlSet)


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
            for ch in self._parser.fetch_dicts_from_list(k, v, 'change'):
                self.changes.append(self._parser.parse_inner_change(
                    ch, self.__change_type))
        elif k == 'catalog' or k == 'catalogname':
            self.catalog_name = str(v).strip()
        elif k == 'schema' or k == 'schemaname':
            self.schema_name = str(v).strip()
        elif k == 'name' or k in self.__name_keys:
            self.name = str(v).strip()
        elif k == 'space' or k == 'tablespace':
            self.table_space = str(v).strip()
        elif k == 'constraints':
            for ch in self._parser.fetch_dicts_from_list(k, v, 'constraint'):
                # FIXME this could be bad - name may not be parsed yet
                if self.name is None:
                    print("** WARNING: parsing constraint before name is known")
                self.constraints.append(self._parser.parse_constraint(
                    self.name, ch))
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

    def make(self, d):
        """
        :param d: dict
        :return: SqlString
        """
        assert isinstance(d, dict)

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'syntax':
                self.syntax = v.strip().lower()
            elif k == 'platforms':
                self.set_platforms(v)
            elif k == 'sql' or k == 'query':
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
        raise Exception("not implemented")

    def parse(self, source, stream):
        """
        Parses the input stream, and returns a list of top-level Change
        instances and SchemaObject values.

        :param stream: Python stream type
        :return: tuple(SchemaVersion)
        """
        raise Exception("not implemented")

    @property
    def source(self):
        return self.__current_source

    def next_order(self, source=None):
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

    def _parse_dict(self, source, d):
        """
        Takes a dictionary of values, similar to a JSon object, and returns
        the parsed schema values.  Used only for the top-level dictionary.

        :param d: dictionary with string keys, and values of lists, strings,
            numerics, nulls, or dictionaries.
        :return:
        """
        self.__current_source = source
        try:
            if not isinstance(d, dict):
                self.error("top level must be a dictionary")
            ret = []

            for (k, v) in d.items():
                k = _strip_key(k)
                if k == 'changes':
                    for ch in self.fetch_dicts_from_list(k, v, 'change'):
                        ret.append(self._parse_top_change(ch))
                elif k == 'change':
                    ret.append(self._parse_top_change(v))
                elif k == 'tables':
                    for ch in self.fetch_dicts_from_list(k, v, 'table'):
                        ret.append(self._parse_table(ch))
                elif k == 'table':
                    ret.append(self._parse_table(v))
                elif k == 'views':
                    for ch in self.fetch_dicts_from_list(k, v, 'view'):
                        ret.append(self._parse_view(ch))
                elif k == 'view':
                    ret.append(self._parse_view(v))
                elif k == 'procedures':
                    for ch in self.fetch_dicts_from_list(k, v, 'procedure'):
                        ret.append(self._parse_procedure(ch))
                elif k == 'procedure':
                    ret.append(self._parse_procedure(v))
                elif k == 'sequences':
                    for ch in self.fetch_dicts_from_list(k, v, 'sequence'):
                        ret.append(self._parse_sequence(ch))
                elif k == 'sequence':
                    ret.append(self._parse_sequence(v))
                else:
                    self.error("unknown key (" + k + ") set to " + repr(v))
        finally:
            self.__current_source = None
        return ret

    def _parse_top_change(self, d):
        if not isinstance(d, dict):
            self.error("top change value is not a dictionary")

        change_obj = BaseObjectBuilder(self)
        sql_set = []
        schema_type = None
        change_type = SQL_CHANGE

        for (k, v) in d.items():
            k = _strip_key(k)
            if change_obj.parse(k, v):
                # handled implicitly
                pass
            elif k == 'schema' or k == 'schematype':
                schema_type = _parse_schema_type(v)
            elif k == 'change' or k == 'changetype':
                change_type = _parse_change_type(v)
            elif k == 'dialects':
                for ch in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(ch))
            elif k in ['statement', 'sql', 'query', 'execute']:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(ch))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if change_type != SQL_CHANGE:
            self.error("only sql changes supported at top-level")
        if schema_type is None:
            self.error("did not specify schema type for change")

        return SqlChange(change_obj.order, change_obj.comment, schema_type,
                         SqlSet(sql_set, None))

    def _parse_table(self, d):
        if not isinstance(d, dict):
            self.error('"table" must be a dictionary')

        table_obj = NameSpaceObjectBuilder(self, ['tablename'], TABLE_TYPE,
                                           False)
        columns = []
        wheres = []
        extended = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if table_obj.parse(k, v):
                # handled by parse
                pass
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                for ch in self.fetch_dicts_from_list(k, v, 'column'):
                    columns.append(self._parse_column(ch))
            elif k in ['wheres', 'whereclauses']:
                for ch in self.fetch_dicts_from_list(k, v, 'where'):
                    wheres.append(self._parse_where(ch))
            elif k in ['extendedactions', 'extendedsql', 'extendsql', 'extend']:
                for ch in self.fetch_dicts_from_list(k, v, 'sql'):
                    extended.append(self._parse_extended_sql(ch))
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
                for ch in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(ch))
            elif k in ['statement', 'sql', 'query', 'execute']:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(ch))
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                for ch in self.fetch_dicts_from_list(k, v, 'column'):
                    columns.append(self._parse_column(ch))
            elif k in ['wheres', 'whereclauses']:
                for ch in self.fetch_dicts_from_list(k, v, 'where'):
                    wheres.append(self._parse_where(ch))
            elif k in ['extendedactions', 'extendedsql', 'extendsql', 'extend']:
                for ch in self.fetch_dicts_from_list(k, v, 'sql'):
                    extended.append(self._parse_extended_sql(ch))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        assert len(sql_set) > 0
        return View(view_obj.order, view_obj.comment, view_obj.catalog_name,
                    replace_if_exists, view_obj.schema_name, view_obj.name,
                    SqlSet(sql_set, None), columns, view_obj.constraints,
                    view_obj.changes, wheres, extended)

    def _parse_procedure(self, d):
        raise Exception("not implemented")

    def _parse_sequence(self, d):
        raise Exception("not implemented")

    def parse_inner_change(self, d, schema_type):
        assert isinstance(d, dict)

        change_obj = BaseObjectBuilder(self)
        sql_set = []
        change_type = SQL_CHANGE

        for (k, v) in d.items():
            k = _strip_key(k)
            if change_obj.parse(k, v):
                # handled
                pass
            elif k == 'schema' or k == 'schematype':
                schema_type = _parse_schema_type(v)
            elif k == 'change' or k == 'changetype' or k == 'type':
                change_type = _parse_change_type(v)
            elif k == 'dialects':
                for ch in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(ch))
            elif k in ['statement', 'sql', 'query', 'execute']:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(ch))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if change_type == SQL_CHANGE:
            if len(sql_set) <= 0:
                return self.error("requires 'sql' or 'dialects' for sql change")
            return SqlChange(change_obj.order, change_obj.comment, schema_type,
                             SqlSet(sql_set, None))
        else:
            return Change(change_obj.order, change_obj.comment, schema_type,
                          change_type)

    def _parse_column(self, d):
        assert isinstance(d, dict)

        column_obj = BaseObjectBuilder(self)
        name = None
        value_type = None
        value = None
        default_value = None
        auto_increment = False
        remarks = None
        before_column = None
        after_column = None
        position = None
        constraints = []
        changes = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if column_obj.parse(k, v):
                # Handled
                pass
            elif k == 'change':
                changes.append(self.parse_inner_change(v, COLUMN_TYPE))
            elif k == 'changes':
                for ch in self.fetch_dicts_from_list(k, v, 'change'):
                    changes.append(self.parse_inner_change(ch, COLUMN_TYPE))
            elif k == 'name':
                name = str(v).strip()
            elif k == 'type':
                value_type = str(v).strip()
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
                for ch in self.fetch_dicts_from_list(k, v, 'constraint'):
                    constraints.append(self.parse_constraint(name, ch))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        assert name is not None and len(name) > 0
        assert value_type is not None and len(value_type) > 0
        return Column(column_obj.order, column_obj.comment, name, value_type,
                      value, default_value, auto_increment, remarks,
                      before_column, after_column, position, constraints,
                      changes)
    
    def _parse_where(self, d):
        assert isinstance(d, dict)

        name = None
        sql_sets = []
        arguments = []
        
        for  (k, v) in d.items():
            k = _strip_key(k)
            if k == 'dialects':
                for ch in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(ch))
            elif k in ['sql', 'value']:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(ch))
            elif k == 'name':
                name = v.strip()
            elif k == 'argument':
                arguments.append(v.strip())
            elif k == 'arguments':
                arguments.extend(self._parse_arguments(k, v))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))
        if len(sql_sets) <= 0:
            self.error("no sql or dialects set for where clause")
        
        return WhereClause(name, SqlSet(sql_sets, arguments))

    def _parse_extended_sql(self, d):
        assert isinstance(d, dict)

        name = None
        sql_sets = []
        sql_type = None
        arguments = []
        
        for (k, v) in d.items():
            if k in ['schematype', 'type', 'operation']:
                assert isinstance(v, str)
                sql_type = v.strip()
            elif k == 'dialects':
                for ch in self.fetch_dicts_from_list(
                        k, v, ['dialect']):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(ch))
            elif k in ['statement', 'sql', 'query', 'execute']:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(ch))
            elif k == 'name':
                name = v.strip()
            elif k == 'argument':
                arguments.append(v.strip())
            elif k == 'arguments':
                arguments.extend(self._parse_arguments(k, v))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))
                
        if len(sql_sets) <= 0:
            self.error("no sql or dialects set for extended sql")
        
        return ExtendedSql(name, sql_type, SqlSet(sql_sets, arguments))

    def parse_constraint(self, parent_column, d):
        assert isinstance(d, dict)

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

        for (k, v) in d.items():
            k = _strip_key(k)
            if cons_obj.parse(k, v):
                # Handled
                pass
            elif k == 'change':
                changes.append(self.parse_inner_change(v, CONSTRAINT_TYPE))
            elif k == 'changes':
                for ch in self.fetch_dicts_from_list(k, v, 'change'):
                    changes.append(self.parse_inner_change(
                        ch, CONSTRAINT_TYPE))
            elif k == 'columns':
                if isinstance(v, str):
                    column_names.extend([c.strip() for c in v.split(',')])
                elif isinstance(v, list) or isinstance(v, tuple):
                    d_list = []
                    for c in v:
                        if isinstance(c, str):
                            column_names.append([c.strip()])
                        elif isinstance(c, dict):
                            d_list.append(c)
                        else:
                            raise Exception("columns can be a string, or "
                                            "contain a list of strings or "
                                            "dictionaries")
                    for c in self.fetch_dicts_from_list(k, d_list, 'column'):
                        column_names.append(c.strip())
            elif k == 'type':
                constraint_type = str(v).strip()
            elif k == 'dialects':
                for ch in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_sets.append(sql.make(ch))
            elif k == 'sql' or k == 'value':
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_sets.append(sql.make(ch))
            elif k == 'language':
                language = v.strip().lower()
            elif k == 'code':
                code = v
            elif k == 'name':
                name = v.strip()
            elif k == 'argument':
                arguments.append(v.strip())
            elif k == 'arguments':
                arguments.extend(self._parse_arguments(k, v))
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
            return LanguageConstraint(cons_obj.order, cons_obj.comment,
                                      constraint_type, column_names, details,
                                      language, code, arguments, changes)

        if name is not None:
            return NamedConstraint(cons_obj.order, cons_obj.comment,
                                   constraint_type, column_names, details, name,
                                   changes)

        return Constraint(cons_obj.order, cons_obj.comment, constraint_type,
                          column_names, details, changes)

    def error(self, message):
        raise Exception(str(self.__current_source) + ': ' + str(message))

    def _parse_value_type_value(self, d):
        # FIXME update the value type to support dialects
        if d is None or isinstance(d, str):
            return ValueTypeValue(d, None, None, None, None)

        assert isinstance(d, dict)

        value_obj = BaseObjectBuilder(self)
        sql_set = []
        vt = None
        val = None

        for (k, v) in d.items():
            k = _strip_key(k)
            if value_obj.parse(k, v):
                # Handled
                pass
            if k == 'type':
                vt = str(v).strip()
            # FIXME include "dialects" parsing
            elif k == 'value':
                val = v
            elif k == 'dialects':
                for ch in self.fetch_dicts_from_list(k, v, 'dialect'):
                    sql = SqlStatementBuilder()
                    sql_set.append(sql.make(ch))
            elif k == 'sql':
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': v
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(ch))
            else:
                self.error("unknown key (" + k + ") set to " + repr(v))

        if (vt == 'int' or vt == 'float' or vt == 'double' or
                (vt is not None and vt.startswith('numeric'))):
            return ValueTypeValue(None, val, None, None, None)
        elif vt == 'bool' or vt == 'boolean':
            return ValueTypeValue(None, None, _parse_boolean(val), None, None)
        elif vt == 'date' or vt == 'time' or vt == 'datetime':
            return ValueTypeValue(None, None, None, str(val), None)
        elif vt == 'computed' or vt == 'sql':
            if len(sql_set) < 0 and val is not None and len(val) > 0:
                ch = {
                    'syntax': 'universal',
                    'platforms': 'all',
                    'sql': val
                }
                sql = SqlStatementBuilder()
                sql_set.append(sql.make(ch))
            if len(sql_set) <= 0:
                self.error("computed value types must have a value or dialect")
            return ValueTypeValue(None, None, None, None, SqlSet(sql_set))
        elif vt == 'str' or vt == 'string' or vt == 'char' or vt == 'varchar':
            return ValueTypeValue(str(val), None, None, None, None)
        else:
            self.error("unknown value type " + vt)

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
    
    def _parse_arguments(self, k, v):
        arguments = []
        if isinstance(v, str):
            arguments.extend([a.strip() for a in v.split(',')])
        else:
            d_list = []
            for c in v:
                if isinstance(c, str):
                    arguments.append(c.strip())
                elif isinstance(c, dict):
                    d_list.append(c)
                else:
                    raise Exception("arguments can be a string, or "
                                    "contain a list of strings or "
                                    "dictionaries")
            for c in self.fetch_dicts_from_list(k, d_list, 'argument'):
                arguments.append(c.strip())
        return arguments
        


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
