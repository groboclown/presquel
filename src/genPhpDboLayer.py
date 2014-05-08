#!/usr/bin/python3

import os
import sys
import sqlmigration
import time

FAIL_IF_EXISTS = True

parent_class = None
namespace = None
output_dir = None
schema_by_name = {}

platforms = ['mysql']


def generate_file(schema_obj, processed_columns, read_only):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    class_name = generate_php_name(schema_obj.name)
    file_name = os.path.join(output_dir, class_name + '.php')
    if os.path.exists(file_name) and FAIL_IF_EXISTS:
        raise Exception("Will not overwrite " + file_name)

    table_validations = []
    for constraint in schema_obj.constraints:
        if not isinstance(constraint, sqlmigration.model.TableConstraint):
            raise Exception("expected TableConstraint, found " +
                            str(type(constraint)))
        assert isinstance(constraint, sqlmigration.model.TableConstraint)
        if constraint.constraint_type == 'phpvalidation':
            table_validations.append(ProcessedPhpValidationConstraint(
                None, constraint, 'table', schema_obj.name))

    uses = ''
    if parent_class.count('\\') > 0:
        uses = 'use ' + parent_class[0: parent_class.find('\\')] + ';'

    with open(file_name, 'w') as f:
        f.writelines(line + '\n' for line in [
            '<?php',
            '',
            'namespace ' + namespace + ';',
            '',
            'use PDO;',
            uses,
            '', '',
            '/**',
            ' * DBO object for ' + schema_obj.name,
            ' *',
            ' * Generated on ' + time.asctime(time.gmtime(time.time())),
            ' */',
            'class ' + class_name + ' extends ' + parent_class + ' {',
            '    public static $INSTANCE;',
            '    public $errors = array();', '',
            '    private function checkForErrors($db) {',
            '        $errs = $db->errorInfo();',
            '        if ($errs[1] != null) {',
            '            $errors[] = $errs[2];',
            '        }',
            '        return false;',
            '    }', '',
        ])
        f.writelines(line + '\n' for line in generate_read(
            schema_obj, processed_columns))

        if not read_only:
            f.writelines((line + '\n') for line in generate_create(
                schema_obj, processed_columns))
            f.writelines((line + '\n') for line in generate_update(
                schema_obj, processed_columns))
            f.writelines(line + '\n' for line in generate_delete(
                schema_obj, processed_columns))

        f.writelines((line + '\n') for line in generate_validations(
            table_validations, processed_columns))

        f.writelines('\n}\n' + class_name + '::$INSTANCE = new ' +
                     class_name + ';\n')


def generate_read(schema_obj, processed_columns):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    join = ''
    fki = 0
    # include the foreign key here, for reference
    col_names = []
    where_ands = []

    for column in schema_obj.columns:
        handled = False
        for constraint in processed_columns.values:
            assert isinstance(constraint, SqlConstraint)
            if (constraint.command == 'read' and
                    constraint.column == column and
                    constraint.value is not None):
                handled = True
                value = constraint.value
                if constraint.argument:
                    value = value.replace('{' + constraint.argument + '}',
                                          ':' + constraint.argument)
                col_names.append(column.name)
                where_ands.append(value)
        if not handled:
            col_names.append(schema_obj.name + '.' + column.name + ' AS ' +
                             column.name)

    for fk in processed_columns.foreign_keys:
        assert isinstance(fk, ProcessedForeignKeyConstraint)
        fki += 1
        fk_name = 'k' + str(fki)
        # Don't pick up the parent owning object in the join
        if not fk.is_owner and fk.join:
            if fk.is_real_fk:
                join += ' INNER JOIN '
            else:
                join += ' LEFT OUTER JOIN '
            join += (fk.fk_table_name + ' ' + fk_name + ' ON ' + fk_name + '.' +
                     fk.fk_column_name + ' = ' + schema_obj.name + '.' +
                     fk.column_name)
            col_names.append(fk_name + '.' + fk.fk_column_name + ' AS ' +
                             fk.fk_table_name + '__' + fk.fk_column_name)
    sql = 'SELECT ' + ','.join(col_names) + ' FROM ' + schema_obj.name + join
    if len(where_ands) > 0:
        sql += ' WHERE ' + (' AND '.join(where_ands))

    ret = [
        '',
        '    public function countAll($db) {',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' +
        schema_obj.name + '\');',
        '        $stmt->execute();',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        return $stmt->fetchColumn();',
        '    }', '', '',
        '    public function readAll($db, $order = false, $start = -1, '
        '$end = -1) {',
        '        $sql = \'' + sql.replace("'", "''") + ' ORDER BY \';',
        '        if (! $order) {',
        '            $sql .= \'' +
        processed_columns.primary_key_column.name + '\';',
        '        } else {',
        '            $sql .= $order;',
        '        }',
        '        if ($start >= 0 && $end > 0) {',
        '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
        '        }',
        '        $stmt = $db->prepare($sql);',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute();',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        $rows = array();',
        '        foreach ($stmt->fetchAll() as $row) {',
        '            if (!$this->validateRead($row)) {',
        '                return False;',
        '            }',
        '            $rows[] = $row;',
        '        }',
        '        return $rows;',
        '    }', '', '',
        '    public function read($db, $id) {',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + ' WHERE ' +
        schema_obj.name + '.' + processed_columns.primary_key_column.name +
        ' = ? LIMIT 1\');',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute(array($id));',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        $row = $stmt->fetch();',
        '        if (!$row) {',
        '            return False;',
        '        }',
        '        if (!$this->validateRead($row)) {',
        '            return False;',
        '        }',
        '        return $row;',
        '    }', '', '',
        '    public function countAny($db, $whereClause, $data) {',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' +
        schema_obj.name + ' \'.$whereClause);',
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        return $stmt->fetchColumn();',
        '    }', '', '',
        '    public function readAny($db, $query, $data, $start = -1, '
        '$end = -1) {',
        '        if ($start >= 0 && $end > 0) {',
        '            $query .= \' LIMIT \'.$start.\',\'.$end;',
        '        }',
        '        $stmt = $db->prepare($query);',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute();',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        $rows = $stmt->fetchAll();',
        '        return $rows;',
        '    }',
        '',
    ]

    for readby in processed_columns.table_reads:
        title = '_x_'.join(col.replace('.', '__') for col in readby)
        arglist = [('$' + col.replace('.', '__')) for col in readby]
        args = ', '.join(arglist)
        readbysql = sql
        if len(where_ands) > 0:
            readbysql += ' AND '
        else:
            readbysql += ' WHERE '
        readbysql += (' AND '.join((col + ' = ?' for col in readby)))
        ret.extend([
            '',
            '    public function countBy' + title + '($db, ' + args + ') {',
            '        $sql = \'' + readbysql.replace("'", "''") + '\';',
            '        $stmt = $db->prepare($sql);',
            '        $stmt->execute(array(' + args + '));',
            '        if ($this->checkForErrors($db)) { return false; }',
            '        return $stmt->fetchColumn();',
            '    }', '' '',
            '    public function readBy' + title + '($db, ' + args +
            ', $order = false, $start = -1, $end = -1) {',
            '        $sql = \'' + readbysql.replace("'", "''") +
            ' ORDER BY \';',
            '        if (! $order) {',
            '            $sql = \'' + processed_columns.
            primary_key_column.name + '\';',
            '        } else {',
            '            $sql = $order;',
            '        }',
            '        if ($start >= 0 && $end > 0) {',
            '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
            '        }',
            '        $stmt = $db->prepare($sql);',
            '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
            '        $stmt->execute(array(' + args + '));',
            '        if ($this->checkForErrors($db)) { return false; }',
            '        $rows = array();',
            '        foreach ($stmt->fetchAll() as $row) {',
            '            if (!$this->validateRead($row)) {',
            '                return false;',
            '            }',
            '            $rows[] = $row;',
            '        }',
            '        return $rows;',
            '    }',
            ''
        ])

    # FIXME do this for ALL keys and indicies.  Also include table indicies that
    # are multi-column.
    for fk in processed_columns.foreign_keys:
        assert isinstance(fk, ProcessedForeignKeyConstraint)
        if fk.is_owner:
            readbysql = sql
            if len(where_ands) > 0:
                readbysql += ' AND '
            else:
                readbysql += ' WHERE '
            readbysql += fk.column_name + ' = ?'

            ret.extend([
                '',
                '    public function countFor' + fk.php_name + '($db, $id) {',
                '        $sql = \'' + readbysql.replace("'", "''") + '\';',
                '        $stmt = $db->prepare($sql);',
                '        $stmt->execute(array($id));',
                '        if ($this->checkForErrors($db)) { return false; }',
                '        return $stmt->fetchColumn();',
                '    }', '', '',
                '    public function readFor' + fk.php_name +
                '($db, $id, $order = false, $start = -1, $end = -1) {',
                '        $sql = \'' + readbysql.replace("'", "''") +
                ' ORDER BY \';',
                '        if (! $order) {',
                '            $sql = \'' + processed_columns.
                primary_key_column.name + '\';',
                '        } else {',
                '            $sql = $order;',
                '        }',
                '        if ($start >= 0 && $end > 0) {',
                '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
                '        }',
                '        $stmt = $db->prepare($sql);',
                '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
                '        $stmt->execute(array($id));',
                '        if ($this->checkForErrors($db)) { return false; }',
                '        $rows = array();',
                '        foreach ($stmt->fetchAll() as $row) {',
                '            if (!$this->validateRead($row)) {',
                '                return False;',
                '            }',
                '            $rows[] = $row;',
                '        }',
                '        return $rows;',
                '    }',
                '',
            ])

    return ret


def generate_create(schema_obj, processed_columns):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    # TODO allow for updating the query to properly handle default values.
    # For now, you'll need an "initial value" and custom sql.

    column_names = []
    values = []
    for column in schema_obj.columns:
        if column != processed_columns.primary_key_column:
            handled = False

            for constraint in processed_columns.values:
                assert isinstance(constraint, SqlConstraint)
                if (constraint.command == 'create' and
                        constraint.value is not None and
                        constraint.column == column):
                    handled = True
                    column_names.append(column.name)
                    value = constraint.value
                    if constraint.argument is not None:
                        value = value.replace('{' + constraint.argument + '}',
                                              ':' + constraint.argument)
                    values.append(value)

            if not handled:
                column_names.append(column.name)
                values.append(':' + column.name)
    cns = []
    cns.extend(column_names)
    sql = ('INSERT INTO ' + schema_obj.name + ' (' +
           (','.join(cns)) +
           ') VALUES (' + (','.join(values)) + ')')

    ret = [
        '',
        '    public function create($db, $data) {',
        '        if (! $this->validateWrite($data)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        $id = $db->lastInsertId();',
        '        $data["' + processed_columns.primary_key_column.name +
        '"] = $id;',
        '        return $data;',
        '    }',
        ''
    ]

    return ret


def generate_update(schema_obj, processed_columns):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    column_order = []
    column_name_values = {}
    for column in schema_obj.columns:
        if column != processed_columns.primary_key_column:
            handled = False
            for constraint in processed_columns.values:
                assert isinstance(constraint, SqlConstraint)
                if (constraint.command == 'update' and
                        constraint.column == column):
                    if constraint.constant:
                        # No update allowed
                        handled = True
                    elif constraint.value is not None:
                        value = constraint.value
                        if constraint.syntax != 'native':
                            raise Exception(
                                "value constraints can only be native")
                        if constraint.argument is not None:
                            value = value.replace(
                                '{' + constraint.argument + '}',
                                ':' + constraint.argument)
                        handled = True
                        column_order.append(column.name)
                        column_name_values[column.name] = value
            if not handled:
                column_order.append(column.name)
                column_name_values[column.name] = ':' + column.name

    sql = 'UPDATE ' + schema_obj.name + ' SET ' +\
          (','.join((cn + ' = ' + column_name_values[cn])
                    for cn in column_order)) +\
          ' WHERE ' + processed_columns.primary_key_column.name + ' = :' + \
          processed_columns.primary_key_column.name

    ret = [
        '',
        '    public function update($db, $data) {',
        '        if (! $this->validateWrite($data)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        return $data;',
        '    }', ''
    ]

    return ret


def generate_delete(schema_obj, processed_columns):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    sql = ('DELETE FROM ' + schema_obj.name + ' WHERE ' + processed_columns.
           primary_key_column.name + ' = :' +
           processed_columns.primary_key_column.name)

    ret = [
        '',
        '    public function remove($db, $data) {',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        return true;',
        '    }'
        '',
    ]

    return ret


def generate_validations(table_validations, processed_columns):
    assert isinstance(processed_columns, ProcessedColumnSet)

    table_validates = [
        '',
        '    private function validateTable(&$row) {',
        '        $ret = True;',
    ]
    read_validates = [
        '',
        '    private function validateRead(&$row) {',
        '        $ret = True;',
    ]
    write_validates = [
        '',
        '    private function validateWrite(&$row) {',
        '        $ret = $this->validateTable($row);',
    ]

    ret = []

    # Always run the validation, by having it appear before the '&& $ret',
    # so that the parent class can collect all of the validation errors.

    for v in processed_columns.php_read:
        assert isinstance(v, ProcessedPhpValidationConstraint)
        read_validates.append('        $ret = $this->validate' + v.order_name +
                              '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns.php_write:
        assert isinstance(v, ProcessedPhpValidationConstraint)
        write_validates.append('        $ret = $this->validate' + v.order_name +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns.php_validation:
        assert isinstance(v, ProcessedPhpValidationConstraint)
        write_validates.append('        $ret = $this->validate' + v.order_name +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))

    for validation in table_validations:
        assert isinstance(validation, ProcessedPhpValidationConstraint)
        table_validates.append('        $ret = $this->validate' +
                               validation.order_name + '($row) && $ret;')
        ret.extend(generate_validation(validation))

    table_validates.extend(['        return $this->finalCheck($ret);', '    }',
                            ''])
    read_validates.extend(['        return $this->finalCheck($ret);', '    }',
                           ''])
    write_validates.extend(['        return $this->finalCheck($ret);', '    }',
                            ''])
    ret.extend(read_validates)
    ret.extend(write_validates)
    ret.extend(table_validates)
    return ret


def generate_validation(validation):
    assert isinstance(validation, ProcessedPhpValidationConstraint)

    ret = [
        '',
        '    private function validate' + validation.order_name + '(&$row) {',
    ]

    if validation.php_name is not None:
        ret.append('        $' + validation.php_name + ' = $row["' +
                   validation.php_name + '"];')
    ret.extend([
        '        return $this->ensure(' + ('            '.join(
        line for line in validation.script.splitlines())) + ', "' +
        validation.column_name + '");', '    }', ''
    ])
    return ret


class AbstractProcessedConstraint(object):
    def __init__(self, column, constraint, name=None):
        assert isinstance(column, sqlmigration.model.Column)
        assert isinstance(constraint, sqlmigration.model.ColumnConstraint)

        object.__init__(self)
        self.column = column
        self.constraint = constraint
        self.column_name = name or column.name
        self.php_name = generate_php_name(self.column_name)
        self.order_name = self.php_name + '_' + str(constraint.order)


class ProcessedForeignKeyConstraint(AbstractProcessedConstraint):
    def __init__(self, column, constraint):
        AbstractProcessedConstraint.__init__(self, column, constraint)

        if 'columns' in constraint.details:
            raise Exception(
                column.name + ": we do not handle multiple "
                "column foreign keys")
        self.order_name += '_fk'
        self.is_owner = False
        if ('relationship' in constraint.details and
                constraint.details['relationship'].lower() == 'owner'):
            self.is_owner = True
        self.is_real_fk = constraint.constraint_type == 'foreignkey'
        self.fk_column_name = constraint.details['column']
        self.fk_table_name = constraint.details['table']
        self.remote_table = None
        if self.fk_table_name in schema_by_name:
            self.remote_table = schema_by_name[self.fk_table_name]
        self.join = False
        if ('pull' in constraint.details
                and constraint.details['pull'] == 'always'):
            self.join = True


class ProcessedPhpValidationConstraint(AbstractProcessedConstraint):
    def __init__(self, column, constraint, validation_type, name=None):
        AbstractProcessedConstraint.__init__(self, column, constraint, name)
        self.script = constraint.details['script']
        self.order_name += '_' + validation_type


class SqlConstraint(AbstractProcessedConstraint):

    # FIXME make this better match the SqlString and SqlSet

    def __init__(self, column, constraint, command):
        AbstractProcessedConstraint.__init__(self, column, constraint)
        assert command in ('create', 'update', 'read')
        self.command = command
        self.constant = constraint.constraint_type == 'noupdate'
        self.syntax = None
        if 'syntax' in constraint.details:
            self.syntax = constraint.details['syntax']
        self.argument = None
        if 'argument' in constraint.details:
            self.argument = constraint.details['argument']
        self.value = None
        if 'value' in constraint.details:
            self.value = constraint.details['value']
        self.user_value = self.constant or (
            self.value is not None and self.argument is None)


class ProcessedColumnSet(object):
    def __init__(self, schema_obj):
        object.__init__(self)
        assert (isinstance(schema_obj, sqlmigration.model.Table)
                or isinstance(schema_obj, sqlmigration.model.View))

        self.primary_key_column = None
        self.foreign_keys = []
        self.php_read = []
        self.php_write = []
        self.php_validation = []
        self.table_reads = []
        self.values = []
        for column in schema_obj.columns:
            assert isinstance(column, sqlmigration.model.Column)

            for constraint in column.constraints:
                assert isinstance(constraint,
                                  sqlmigration.model.ColumnConstraint)

                if 'platforms' in constraint.details:
                    plats = [c.strip() for c in
                             constraint.details['platforms'].split(',')]
                    found = False
                    for p in platforms:
                        if p in plats:
                            found = True
                            break
                    if not found:
                        # Do not use this constraint if the platform doesn't
                        # match.
                        continue

                if constraint.constraint_type == 'primarykey':
                    if self.primary_key_column is not None:
                        raise Exception(
                            schema_obj.name + " column " + column.name +
                            " has multiple primary keys")
                    self.primary_key_column = column

                elif (constraint.constraint_type == 'foreignkey'
                        or constraint.constraint_type == 'falseforeignkey'
                        or constraint.constraint_type == 'fakeforeignkey'):
                    self.foreign_keys.append(ProcessedForeignKeyConstraint(
                        column, constraint))

                elif constraint.constraint_type == 'phpvalidation':
                    self.php_validation.append(ProcessedPhpValidationConstraint(
                        column, constraint, 'validation'))
                elif constraint.constraint_type == 'phpread':
                    self.php_read.append(ProcessedPhpValidationConstraint(
                        column, constraint, 'read'))
                elif constraint.constraint_type == 'phpwrite':
                    self.php_write.append(ProcessedPhpValidationConstraint(
                        column, constraint, 'write'))
                elif constraint.constraint_type == 'initialvalue':
                    self.values.append(
                        SqlConstraint(column, constraint, 'create'))
                elif (constraint.constraint_type == 'noupdate' or
                      constraint.constraint_type == 'constantupdate'):
                    self.values.append(
                        SqlConstraint(column, constraint, 'update'))
                elif constraint.constraint_type == 'constantquery':
                    self.values.append(
                        SqlConstraint(column, constraint, 'read'))

        for constraint in schema_obj.constraints:
            assert isinstance(constraint, sqlmigration.model.TableConstraint)

            if constraint.constraint_type == 'read':
                self.table_reads.append(
                    [col.strip() for col in
                        constraint.details['columns'].split(',')])

        if self.primary_key_column is None:
            raise Exception("No primary keys found")


def generate_php_name(schema_name):
    first = True
    ret = ''
    for c in schema_name:
        if c == '_':
            first = True
        else:
            if first:
                c = c.upper()
                first = False
            else:
                c = c.lower()
            ret += c
    assert len(ret) > 0
    return ret


if __name__ == '__main__':
    (parent_class, namespace, in_dir, output_dir) = sys.argv[1:]
    versions = sqlmigration.parse_versions(in_dir)
    if len(versions) <= 0:
        raise Exception("no versions found")

    head = versions[0]
    processed_column_map = {}

    # Step 1: process all the columns
    for schema in head.schema:
        if (isinstance(schema, sqlmigration.model.Table)
                or isinstance(schema, sqlmigration.model.View)):
            processed_column_map[schema] = ProcessedColumnSet(schema)
            schema_by_name[schema.name] = schema

    for schema in head.schema:
        if isinstance(schema, sqlmigration.model.Table):
            print("Table " + schema.name)
            generate_file(schema, processed_column_map[schema], False)
        elif isinstance(schema, sqlmigration.model.View):
            print("View " + schema.name)
            generate_file(schema, processed_column_map[schema], True)
