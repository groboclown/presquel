
from ..model import (SCHEMA_OBJECT_TYPES, CHANGE_TYPES,
                     SQL_CHANGE, SqlChange, Change,
                     TABLE_TYPE, Table,
                     VIEW_TYPE, View, CONSTRAINT_TYPE, COLUMN_TYPE,
                     Column, ColumnConstraint, TableConstraint, ValueTypeValue)


class SchemaParser(object):
    """
    Note: not thread safe.
    """

    def __init__(self):
        object.__init__(self)
        self.__count = 0
        self.__source = None

    def parse(self, source, stream):
        """
        Parses the input stream, and returns a list of top-level Change
        instances and SchemaObject values.

        :param stream: Python stream type
        :return: tuple(SchemaVersion)
        """
        raise Exception("not implemented")

    def _parse_dict(self, source, d):
        """
        Takes a dictionary of values, similar to a JSon object, and returns
        the parsed schema values.

        :param d: dictionary with string keys, and values of lists, strings,
            numerics, nulls, or dictionaries.
        :return:
        """
        self.__source = source
        if not isinstance(d, dict):
            self._error("top level must be a dictionary")
        ret = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'changes':
                if not (isinstance(v, tuple) or isinstance(v, list)):
                    self._error("changes does not contain a list, but " +
                                repr(v))
                for ch in v:
                    for (kk, vv) in v.items():
                        kk = _strip_key(kk)
                        if kk == 'change':
                            ret.append(self._parse_top_change(ch))
                        else:
                            self._error('"changes" can only contain "change')
            elif k == 'change':
                ret.append(self._parse_top_change(v))
            elif k == 'table':
                ret.append(self._parse_table(v))
            elif k == 'view':
                ret.append(self._parse_view(v))
            elif k == 'procedure':
                ret.append(self._parse_procedure(v))
            elif k == 'sequence':
                ret.append(self._parse_sequence(v))
            else:
                self._parse_common_keyval(k, v)
        return ret

    def _parse_top_change(self, d):
        if not isinstance(d, dict):
            self._error("top change value is not a dictionary")

        comment = None
        order = self.__count
        self.__count += 1
        schema_type = None
        change_type = SQL_CHANGE
        sql = None
        platforms = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                if not isinstance(v, str):
                    self._error('"comment" can only be a string')
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'schema' or k == 'schema':
                schema_type = _parse_schema_type(v)
            elif k == 'change' or k == 'changetype':
                change_type = _parse_change_type(v)
            elif k == 'sql':
                if not isinstance(v, str):
                    self._error('"sql" can only be a string')
                sql = v
            elif k == 'platform':
                platforms.append(str(v).strip())
            elif k == 'platforms':
                if not (isinstance(v, tuple) or isinstance(v, list)):
                    self._error('"platforms" can only contain a list')
                for p in v:
                    if isinstance(p, str):
                        platforms.append(p.strip())
                    else:
                        for (kk, vv) in p.items():
                            kk = _strip_key(kk)
                            if kk == 'platform':
                                platforms.append(str(vv).strip())
                            else:
                                self._error('"platforms" can only contain '
                                            '"platform" or a list of strings')
            else:
                self._parse_common_keyval(k, v)

        if schema_type is None:
            self._error("did not specify schema type for change")
        if change_type != SQL_CHANGE:
            self._error("only sql changes supported at top-level")
        if sql is None or len(sql) <= 0:
            self._error("requires 'sql' for sql change")
        return SqlChange(order, comment, schema_type, platforms, sql)

    def _parse_table(self, d):
        if not isinstance(d, dict):
            self._error('"table" must be a dictionary')

        comment = None
        order = self.__count
        self.__count += 1
        catalog_name = None
        schema_name = None
        table_name = None
        table_space = None
        columns = []
        constraints = []
        changes = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'change':
                changes.append(self._parse_inner_change(v, TABLE_TYPE))
            elif k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    for (kk, vv) in ch.items():
                        kk = _strip_key(kk)
                        if kk == 'change':
                            changes.append(self._parse_inner_change(
                                vv, TABLE_TYPE))
                        else:
                            self._error('only "change" is allowed inside '
                                        '"changes"')
            elif k == 'catalog' or k == 'catalogname':
                catalog_name = str(v).strip()
            elif k == 'schema' or k == 'schemaname':
                schema_name = str(v).strip()
            elif k == 'name' or k == 'tablename':
                table_name = str(v).strip()
            elif k == 'space' or k == 'tablespace':
                table_space = str(v).strip()
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                assert isinstance(v, tuple) or isinstance(v, list)
                for col in v:
                    for (kk, vv) in col.items():
                        kk = _strip_key(kk)
                        if kk == 'column':
                            columns.append(self._parse_column(vv))
                        else:
                            self._error('only "column" is allowed inside '
                                        '"columns"')
            elif k == 'constraints':
                if not (isinstance(v, tuple) or isinstance(v, list)):
                    self._error('"constraints" must be a list of "constraint", '
                                'but found ' + repr(v))
                for con in v:
                    for (kk, vv) in con.items():
                        if kk == 'constraint':
                            constraints.append(
                                self._parse_constraint(vv, False))
                        else:
                            self._error('"constraints" must contain only'
                                        ' "constraint", but found ' + repr(kk))
            else:
                self._parse_common_keyval(k, v)

        assert table_name is not None and len(table_name) > 0
        return Table(order, comment, catalog_name, schema_name, table_name,
                     table_space, columns, constraints, changes)

    def _parse_view(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        catalog_name = None
        replace_if_exists = True
        schema_name = None
        view_name = None
        select_query = None
        columns = []
        constraints = []
        changes = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'change':
                changes.append(self._parse_inner_change(v, VIEW_TYPE))
            elif k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    for (kk, vv) in ch.items():
                        kk = _strip_key(kk)
                        if kk == 'change':
                            changes.append(self._parse_inner_change(
                                vv, VIEW_TYPE))
                        else:
                            self._error('only "change" is allowed inside '
                                        '"changes"')
            elif k == 'catalog' or k == 'catalogname':
                catalog_name = str(v).strip()
            elif k == 'schema' or k == 'schemaname':
                schema_name = str(v).strip()
            elif k == 'name' or k == 'viewname':
                view_name = str(v).strip()
            elif k == 'replace' or k == 'replaceifexists':
                replace_if_exists = _parse_boolean(v)
            elif k == 'query' or k == 'select' or k == 'sql':
                select_query = str(v)
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                assert isinstance(v, tuple) or isinstance(v, list)
                for col in v:
                    columns.append(self._parse_column(col))
            elif k == 'constraints':
                if not (isinstance(v, tuple) or isinstance(v, list)):
                    self._error('"constraints" must be a list of "constraint", '
                                'but found ' + repr(v))
                for con in v:
                    for (kk, vv) in con.items():
                        if kk == 'constraint':
                            constraints.append(
                                self._parse_constraint(vv, False))
                        else:
                            self._error('"constraints" must contain only'
                                        ' "constraint", but found ' + repr(kk))
            else:
                self._parse_common_keyval(k, v)

        assert select_query is not None and len(select_query) > 0
        return View(order, comment, catalog_name, replace_if_exists,
                    schema_name, view_name, select_query, columns, constraints,
                    changes)

    def _parse_procedure(self, d):
        raise Exception("not implemented")

    def _parse_sequence(self, d):
        raise Exception("not implemented")

    def _parse_inner_change(self, d, schema_type):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        change_type = SQL_CHANGE
        sql = None
        platforms = []

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'schema' or k == 'schematype':
                schema_type = _parse_schema_type(v)
            elif k == 'change' or k == 'changetype':
                change_type = _parse_change_type(v)
            elif k == 'sql':
                assert isinstance(v, str)
                sql = v
            elif k == 'platform':
                platforms.append(str(v).strip())
            elif k == 'platforms':
                assert isinstance(v, tuple) or isinstance(v, list)
                for p in v:
                    platforms.append(p.strip())
            else:
                self._parse_common_keyval(k, v)

        if change_type == SQL_CHANGE:
            if sql is None or len(sql) <= 0:
                return self._error("requires 'sql' for sql change")
            return SqlChange(order, comment, schema_type, sql, platforms)
        else:
            return Change(order, comment, schema_type, change_type)

    def _parse_column(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
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
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'change':
                changes.append(self._parse_inner_change(v, COLUMN_TYPE))
            elif k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    changes.append(self._parse_inner_change(ch, COLUMN_TYPE))
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
                if not (isinstance(v, tuple) or isinstance(v, list)):
                    self._error('"constraints" must be a list of "constraint", '
                                'but found '+repr(v))
                for con in v:
                    for (kk, vv) in con.items():
                        if kk == 'constraint':
                            constraints.append(
                                self._parse_constraint(vv, True))
                        else:
                            self._error('"constraints" must contain only'
                                        ' "constraint", but found ' + repr(kk))
            else:
                self._parse_common_keyval(k, v)

        assert name is not None and len(name) > 0
        assert value_type is not None and len(value_type) > 0
        return Column(order, comment, name, value_type, value, default_value,
                      auto_increment, remarks, before_column, after_column,
                      position, constraints, changes)

    def _parse_constraint(self, d, is_column):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        constraint_type = None
        changes = []
        details = {}

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'change':
                changes.append(self._parse_inner_change(v, CONSTRAINT_TYPE))
            elif k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    for (kk, vv) in ch.items():
                        kk = _strip_key(kk)
                        if kk == 'change':
                            changes.append(self._parse_inner_change(
                                vv, CONSTRAINT_TYPE))
                        else:
                            self._error('only "change" is allowed inside '
                                        '"changes"')
            elif k == 'type':
                constraint_type = str(v).strip()
            else:
                if not self._parse_common_keyval(k, v, False):
                    details[k] = v

        assert constraint_type is not None and len(constraint_type) > 0
        if is_column:
            return ColumnConstraint(order, comment, constraint_type, details,
                                    changes)
        else:
            return TableConstraint(order, comment, constraint_type, details,
                                   changes)

    def _parse_table_constraint(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        constraint_type = None
        changes = []
        details = {}

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif k == 'change':
                changes.append(self._parse_inner_change(v, CONSTRAINT_TYPE))
            elif k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    for (kk, vv) in ch.items():
                        kk = _strip_key(kk)
                        if kk == 'change':
                            changes.append(self._parse_inner_change(
                                vv, CONSTRAINT_TYPE))
                        else:
                            self._error('only "change" is allowed inside '
                                        '"changes"')
            elif k == 'type':
                constraint_type = str(v).strip()
            else:
                if not self._parse_common_keyval(k, v, False):
                    details[k] = v

        assert constraint_type is not None and len(constraint_type) > 0
        return TableConstraint(order, comment, constraint_type, details,
                               changes)

    def _error(self, message):
        raise Exception(str(self.__source) + ': ' + str(message))

    def _parse_common_keyval(self, k, v, fail = True):
        if k == 'error':
            raise Exception(str(self.__source) + ': defines error "' + str(v) +
                            '"')
        elif k == 'warning':
            print("**WARNING** (" + str(self.__source) + ")", str(v))
        elif  k == 'note':
            print("Note (" + str(self.__source) + ")", str(v))
        elif fail:
            raise Exception(str(self.__source) + ": unknown key: " + str(k))
        else:
            return False
        return True

    def _parse_value_type_value(self, d):
        if d is None or isinstance(d, str):
            return ValueTypeValue(d, None, None, None, None)

        assert isinstance(d, dict)

        vt = None
        val = None

        for (k, v) in d.items():
            k = _strip_key(k)
            if k == 'type':
                vt = str(v).strip()
            elif k == 'value':
                val = v
            else:
                self._parse_common_keyval(k, v)

        if (vt == 'int' or vt == 'float' or vt == 'double' or
                (vt is not None and vt.startswith('numeric'))):
            return ValueTypeValue(None, val, None, None, None)
        elif vt == 'bool' or vt == 'boolean':
            return ValueTypeValue(None, None, _parse_boolean(val), None, None)
        elif vt == 'date' or vt == 'time' or vt == 'datetime':
            return ValueTypeValue(None, None, None, str(val), None)
        elif vt == 'computed' or vt == 'sql':
            return ValueTypeValue(None, None, None, None, str(val))
        elif vt == 'str' or vt == 'string' or vt == 'char' or vt == 'varchar':
            return ValueTypeValue(str(val), None, None, None, None)


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
