#!/usr/bin/python3

import os
import sys
import sqlmigration
import time

FAIL_IF_EXISTS = True

parent_class = None
namespace = None
output_dir = None


def generate_file(schema_name, columns, table_constraints, read_only):
    class_name = generate_php_name(schema_name)
    file_name = os.path.join(output_dir, class_name + '.php')
    if os.path.exists(file_name) and FAIL_IF_EXISTS:
        raise Exception("Will not overwrite " + file_name)

    processed_columns = process_columns(schema_name, columns)
    table_validations = []
    for constraint in table_constraints:
        assert isinstance(constraint, sqlmigration.model.TableConstraint)
        if constraint.constraint_type == 'phpvalidation':
            table_validations.append(['Table', None,
                                      'Table' + str(constraint.order),
                                      constraint.details['script']])

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
            ' * DBO object for ' + schema_name,
            ' *',
            ' * Generated on ' + time.asctime(time.gmtime(time.time())),
            ' */',
            'class ' + class_name + ' extends ' + parent_class + ' {',
        ])
        f.writelines(line + '\n' for line in
                     generate_read(schema_name, columns, processed_columns))

        if not read_only:
            f.writelines(line + '\n' for line in
                         generate_create(schema_name, columns,
                                         processed_columns))
            f.writelines(line + '\n' for line in
                         generate_update(schema_name, columns,
                                         processed_columns))
            f.writelines(line + '\n' for line in
                         generate_delete(schema_name, columns,
                                         processed_columns))

        f.writelines(line + '\n' for line in
                     generate_validations(table_validations, processed_columns))

        f.writelines('\n}\n')


def generate_read(schema_name, columns, processed_columns):
    sql = 'SELECT * FROM ' + schema_name
    for fk in processed_columns['foreign_keys']:
        if not fk[5]:
            sql += ' INNER JOIN ' + fk[3] + ' ON ' + fk[3] + '.' + fk[4] +\
                   ' = ' + schema_name + '.' + fk[0]

    # TODO make the readAll take an optional "rowStart, rowEnd" argument
    ret = [
        '',
        '    public function countRows($db) {',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' + schema_name +
        '\');',
        '        $stmt->execute();',
        '        return $stmt->fetchColumn();',
        '    }', '', '',
        '    public function readAll($db, $order = false, $start = -1, '
        '$end = -1) {',
        '        $sql = \'' + sql.replace("'", "''") + ' ORDER BY \';',
        '        if (! $order) {',
        '            $sql .= \'' +
        processed_columns['primary_key_column'].name + '\';',
        '        } else {',
        '            $sql .= $oder;',
        '        }',
        '        if ($start >= 0 && $end > 0) {',
        '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
        '        }',
        '        $stmt = $db->prepare($sql);',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute();',
        '        $rows = array();',
        '        foreach ($stmt->fetchAll() as $row) {',
        '            if (!$this->validateRead($row)) {',
        '                return False;',
        '            }',
        '            $rows[] = $row;',
        '        }',
        '        return $rows;',
        '    }', '', '',
        '    public function read($id) {',
        '        if ((! $id && $id != 0) || !is_int($id)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + ' WHERE ' +
        processed_columns['primary_key_column'].name + ' = ?\');',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute($id);',
        '        $row = $stmt->fetch();',
        '        if (!$row) {',
        '            return False;',
        '        }',
        '        if (!$this->validateRead($row)) {',
        '            return False;',
        '        }',
        '        return $row;',
        '    }', ''
    ]
    for fk in processed_columns['foreign_keys']:
        if fk[5]:
            ret.extend([
                '',
                '    public function readFor' + fk[1] +
                '($db, $id, $order = false, $start = -1, $end = -1) {',
                '        if ((! $id && $id != 0) || !is_int($id)) {',
                '            return False;',
                '        }',
                '        $sql = \'' + sql.replace("'", "''") +
                ' WHERE ' + fk[0] + ' = ? ORDER BY \';',
                '        if (! $order) {',
                '            $sql = \'' + processed_columns[
                    'primary_key_column'].name + '\';',
                '        } else {',
                '            $sql = $order;',
                '        }',
                '        if ($start >= 0 && $end > 0) {',
                '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
                '        }',
                '        $stmt = $db->prepare($sql);',
                '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
                '        $stmt->execute(array($id));',
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


def generate_create(schema_name, columns, processed_columns):
    column_names = []
    date_cols = []
    date_vals = []
    for column in columns:
        if column != processed_columns['primary_key_column']:
            # Special handlers for the creation date.  This is specific
            # to the WebRiffs standards
            if column.name.lower() == 'created_on':
                date_cols.append(column.name)
                # MySql flavor
                date_vals.append("NOW()")
            elif column.name.lower() == 'last_updated_on':
                date_cols.append(column.name)
                date_vals.append("NULL")
            else:
                column_names.append(column.name)
    cns = []
    cns.extend(column_names)
    cns.extend(date_cols)
    vals = []
    vals.extend(':' + cn for cn in column_names)
    vals.extend(date_vals)
    sql = ('INSERT INTO ' + schema_name + ' (' +
           (','.join(cns)) +
           ') VALUES (' + (','.join(vals)) + ')')

    ret = [
        '',
        '    public function create($db, $data) {',
        '        if (! $this->validateWrite($data)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        if (! $stmt->execute($data)) {',
        '            $this->insertFailed(\'' + schema_name + '\', $data);',
        '        }',
        '        $id = $db->lastInsertId();',
        '        $data["' + processed_columns['primary_key_column'].name +
        '"] = $id;',
        '        return $data;',
        '    }',
        ''
    ]

    return ret


def generate_update(schema_name, columns, processed_columns):
    column_names = []
    for column in columns:
        if column != processed_columns['primary_key_column']:
            column_names.append(column.name)
    sql = 'UPDATE ' + schema_name +\
          (','.join((' SET ' + cn + ' = :' + cn) for cn in column_names)) +\
          ' WHERE ' + processed_columns['primary_key_column'].name + ' = :' + \
          processed_columns['primary_key_column'].name

    ret = [
        '',
        '    public function update($db, $data) {',
        '        if (! $this->validateWrite($data)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
        '        return $data;',
        '    }', ''
    ]

    return ret


def generate_delete(schema_name, columns, processed_columns):
    sql = 'DELETE FROM ' + schema_name + ' WHERE ' + processed_columns[
        'primary_key_column'].name + ' = :' + \
        processed_columns['primary_key_column'].name

    ret = [
        '',
        '    public function remove($db, $data) {',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
        '        return False;',
        '    }'
        '',
    ]

    return ret


def generate_validations(table_validations, processed_columns):
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
    for v in processed_columns['php_read']:
        read_validates.append('        $ret = $this->validate' + v[2] +
                              '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns['php_write']:
        write_validates.append('        $ret = $this->validate' + v[2] +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns['php_validation']:
        write_validates.append('        $ret = $this->validate' + v[2] +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))

    for validation in table_validations:
        table_validates.append('        $ret = $this->validate' +
                               validation[2] + '($row) && $ret;')
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
    (schema_name, php_name, validation_name, script) = validation

    ret = [
        '',
        '    private function validate' + validation_name + '(&$row) {',
    ]

    if php_name is not None:
        ret.append('        $' + php_name + ' = $row["' + php_name + '"];')
    ret.extend([
        '        return $this->ensure(' + ('            '.join(
        line for line in script.splitlines())) + ', "' + schema_name + '");',
        '    }', ''
    ])
    return ret


def process_columns(schema_name, columns):
    primary_key_column = None
    foreign_keys = []
    php_read = []
    php_write = []
    php_validation = []
    for column in columns:
        assert isinstance(column, sqlmigration.model.Column)
        cn = generate_php_name(column.name)
        for constraint in column.constraints:
            cno = cn + '_' + str(constraint.order)
            assert isinstance(constraint, sqlmigration.model.ColumnConstraint)
            if constraint.constraint_type == 'primarykey':
                if primary_key_column is not None:
                    raise Exception(schema_name + " column " + column.name +
                                    " has multiple primary keys")
                primary_key_column = column
            elif constraint.constraint_type == 'foreignkey':
                if 'columns' in constraint.details:
                    raise Exception(schema_name + ": we do not handle multiple "
                                                  "column foreign keys")
                is_owner = False
                if ('relationship' in constraint.details and
                        constraint.details['relationship'].lower() == 'owner'):
                    is_owner = True
                foreign_keys.append([
                    column.name, cn, cno + '_fk',
                    constraint.details['table'],
                    constraint.details['column'], is_owner])
            elif constraint.constraint_type == 'phpvalidation':
                php_validation.append([
                    column.name, cn, cno,
                    constraint.details['script']
                ])
            elif constraint.constraint_type == 'phpread':
                php_read.append([
                    column.name, cn, cno + '_read',
                    constraint.details['script']
                ])
            elif constraint.constraint_type == 'phpwrite':
                php_write.append([
                    column.name, cn, cno + '_write',
                    constraint.details['script']
                ])
    if primary_key_column is None:
        raise Exception("No primary keys found")
    return {
        'primary_key_column': primary_key_column,
        'foreign_keys': foreign_keys,
        'php_read': php_read,
        'php_write': php_write,
        'php_validation': php_validation
    }


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

    for schema in head.schema:
        if isinstance(schema, sqlmigration.model.Table):
            print("Table " + schema.name)
            generate_file(schema.table_name, schema.columns,
                          schema.table_constraints, False)
        elif isinstance(schema, sqlmigration.model.View):
            print("View " + schema.name)
            generate_file(schema.view_name, schema.columns, [], True)
