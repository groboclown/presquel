
from ..model import (SCHEMA_OBJECT_TYPES, CHANGE_TYPES,
                     SQL_CHANGE, SqlChange, Change,
                     TABLE_TYPE, Table,
                     VIEW_TYPE, View,
                     Column, Constraint, ValueTypeValue)


class SchemaParser(object):
    def __init__(self):
        object.__init__(self)
        self.__count = 0

    def parse(self, stream):
        """
        Parses the input stream, and returns a list of top-level Change
        instances and SchemaObject values.

        :param stream: Python stream type
        :return: tuple(SchemaVersion)
        """
        raise Exception("not implemented")

    def _parse_dict(self, d):
        """
        Takes a dictionary of values, similar to a JSon object, and returns
        the parsed schema values.

        :param d: dictionary with string keys, and values of lists, strings,
            numerics, nulls, or dictionaries.
        :return:
        """
        assert isinstance(d, dict)
        ret = []

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
            if k == 'changes':
                assert isinstance(v, tuple) or isinstance(v, list)
                for ch in v:
                    ret.append(self._parse_top_change(ch))
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
                _parse_common_keyval(k, v)

    def _parse_top_change(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        schema_type = None
        change_type = SQL_CHANGE
        sql = None

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif (k == 'schema' or k == 'schema-type' or k == 'schema type'
                  or k == 'schema_type'):
                schema_type = _parse_schema_type(v)
            elif (k == 'change' or k == 'change-type' or k == 'change type'
                  or k == 'change_type'):
                change_type = _parse_change_type(v)
            elif k == 'sql':
                assert isinstance(v, str)
                sql = v
            else:
                _parse_common_keyval(k, v)

        assert schema_type is not None
        if change_type != SQL_CHANGE:
            raise Exception("only sql changes supported at top-level")
        if sql is None or len(sql) <= 0:
            raise Exception("requires 'sql' for sql change")
        return SqlChange(order, comment, schema_type, sql)

    def _parse_table(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        catalog_name = None
        schema_name = None
        table_name = None
        table_space = None
        columns = []
        changes = []

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
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
                    changes.append(self._parse_inner_change(ch, TABLE_TYPE))
            elif (k == 'catalog' or k == 'catalog-name' or k == 'catalog name'
                  or k == 'catalog_name'):
                catalog_name = str(v).strip()
            elif (k == 'schema' or k == 'schema-name' or k == 'schema name'
                  or k == 'schema_name'):
                schema_name = str(v).strip()
            elif (k == 'name' or k == 'table-name' or k == 'table name'
                  or k == 'table_name'):
                table_name = str(v).strip()
            elif (k == 'space' or k == 'table-space' or k == 'table space'
                  or k == 'table_space'):
                table_space = str(v).strip()
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                assert isinstance(v, tuple) or isinstance(v, list)
                for col in v:
                    columns.append(self._parse_column(col))
            else:
                _parse_common_keyval(k, v)

        assert table_name is not None and len(table_name) > 0
        return Table(order, comment, catalog_name, schema_name, table_name,
                     table_space, columns, changes)

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
        changes = []

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
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
                    changes.append(self._parse_inner_change(ch, VIEW_TYPE))
            elif (k == 'catalog' or k == 'catalog-name' or k == 'catalog name'
                  or k == 'catalog_name'):
                catalog_name = str(v).strip()
            elif (k == 'schema' or k == 'schema-name' or k == 'schema name'
                  or k == 'schema_name'):
                schema_name = str(v).strip()
            elif (k == 'name' or k == 'view-name' or k == 'view name'
                  or k == 'view_name'):
                view_name = str(v).strip()
            elif (k == 'replace' or k == 'replace if exists' or
                  k == 'replace-if-exists' or k == 'replace_if_exists'):
                replace_if_exists = _parse_boolean(v)
            elif k == 'query' or k == 'select' or k == 'sql':
                select_query = str(v)
            elif k == 'column':
                columns.append(self._parse_column(v))
            elif k == 'columns':
                assert isinstance(v, tuple) or isinstance(v, list)
                for col in v:
                    columns.append(self._parse_column(col))
            else:
                _parse_common_keyval(k, v)

        assert select_query is not None and len(select_query) > 0
        return View(order, comment, catalog_name, replace_if_exists,
                    schema_name, view_name, select_query, columns, changes)

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

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
            if k == 'comment':
                assert isinstance(v, str)
                comment = v
            elif k == 'order':
                order = int(v)
            elif (k == 'schema' or k == 'schema-type' or k == 'schema type'
                  or k == 'schema_type'):
                schema_type = _parse_schema_type(v)
            elif (k == 'change' or k == 'change-type' or k == 'change type'
                  or k == 'change_type'):
                change_type = _parse_change_type(v)
            elif k == 'sql':
                assert isinstance(v, str)
                sql = v
            else:
                _parse_common_keyval(k, v)

        if change_type == SQL_CHANGE:
            if sql is None or len(sql) <= 0:
                raise Exception("requires 'sql' for sql change")
            return SqlChange(order, comment, schema_type, sql)
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
            assert isinstance(k, str)
            k = k.strip().lower()
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
                    changes.append(self._parse_inner_change(ch, VIEW_TYPE))
            elif k == 'name':
                name = str(v).strip()
            elif k == 'type':
                value_type = str(v).strip()
            elif k == 'value':
                value = _parse_value_type_value(v)
            elif (k == 'default' or k == 'default-value' or k == 'default value'
                  or k == 'default_value'):
                default_value = _parse_value_type_value(v)
            elif k == 'remarks':
                remarks = str(v)
            elif (k == 'before' or k == 'before-column' or k == 'before column'
                  or k == 'before_column'):
                before_column = str(v).strip()
            elif (k == 'after' or k == 'after-column' or k == 'after column'
                  or k == 'after_column'):
                after_column = str(v).strip()
            elif k == 'position':
                position = int(v)
                assert position >= 0
            elif k == 'constraint':
                constraints.append(self._parse_constraint(v))
            elif k == 'constraints':
                assert isinstance(v, tuple) or isinstance(v, list)
                for con in v:
                    constraints.append(self._parse_constraint(con))
            else:
                _parse_common_keyval(k, v)

        assert name is not None and len(name) > 0
        assert value_type is not None and len(value_type) > 0
        return Column(order, comment, name, value_type, value, default_value,
                      auto_increment, remarks, before_column, after_column,
                      position, constraints, changes)

    def _parse_constraint(self, d):
        assert isinstance(d, dict)

        comment = None
        order = self.__count
        self.__count += 1
        constraint_type = None
        changes = []

        for (k, v) in d.items():
            assert isinstance(k, str)
            k = k.strip().lower()
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
                    changes.append(self._parse_inner_change(ch, VIEW_TYPE))
            elif k == 'type':
                constraint_type = str(v).strip()
            else:
                _parse_common_keyval(k, v)

        assert constraint_type is not None and len(constraint_type) > 0
        return Constraint(order, comment, constraint_type, changes)


def _parse_common_keyval(k, v):
    if k == 'error':
        raise Exception(str(v))
    elif k == 'warning':
        print("**WARNING**", str(v))
    elif  k == 'note':
        print("Note:", str(v))
    else:
        raise Exception("unknown key: " + str(k))


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


def _parse_value_type_value(d):
    if d is None or isinstance(d, str):
        return ValueTypeValue(d, None, None, None, None)

    assert isinstance(d, dict)

    vt = None
    val = None

    for (k, v) in d.items():
        assert isinstance(k, str)
        k = k.strip().lower()
        if k == 'type':
            vt = str(v).strip()
        elif k == 'value':
            val = v
        else:
            _parse_common_keyval(k, v)

    if (vt == 'int' or vt == 'float' or vt == 'double' or
            (vt is not None and vt.startswith('numeric'))):
        return ValueTypeValue(None, val, None, None, None)
    elif vt == 'bool' or vt == 'boolean':
        return ValueTypeValue(None, None, _parse_boolean(v), None, None)
    elif vt == 'date' or vt == 'time' or vt == 'datetime':
        return ValueTypeValue(None, None, None, str(v), None)
    elif vt == 'computed' or vt == 'sql':
        return ValueTypeValue(None, None, None, None, str(v))
    elif vt == 'str' or vt == 'string' or vt == 'char' or vt == 'varchar':
        return ValueTypeValue(str(v), None, None, None, None)
