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
    fks = processed_columns['foreign_keys']
    sql = 'SELECT * FROM ' + schema_name
    for fk in fks:
        sql += ' INNER JOIN ' + fk[3] + ' ON ' + fk[3] + '.' + fk[4] + ' = ' +\
            schema_name + '.' + fk[0]

    # TODO make the readAll take an optional "rowStart, rowEnd" argument
    ret = [
        '',
        '    public function countRows($db) {',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' + schema_name + '\');',
        '        $stmt->execute();',
        '        return $stmt->fetchColumn();',
        '    }', '', '',
        '    public function readAll($db) {',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute();',
        '        $rows = array();',
        '        foreach ($stmt->fetch() as $row) {',
        '            if (!validateRead($row)) {',
        '                return false;',
        '            }',
        '            $rows[] = $row;',
        '        }',
        '        return $rows;',
        '    }', '', '',
        '    public function read($id) {',
        '        if ($id == null || !is_int($id)) {',
        '            return false;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + ' WHERE ' +
        processed_columns['primary_key_column'].name + ' = ?\');',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute($id);',
        '        $row = $stmt->fetch();',
        '        if (!$row) {',
        '            return false;',
        '        }',
        '        if (!validateRead($row)) {',
        '            return false;',
        '        }',
        '        return $row;',
        '    }', ''
    ]

    return ret


def generate_create(schema_name, columns, processed_columns):
    column_names = []
    for column in columns:
        if column != processed_columns['primary_key_column']:
            column_names.append(column.name)
    sql = 'INSERT INTO ' + schema_name + ' (' +\
          (','.join(cn for cn in column_names)) + ') VALUES (' +\
          (','.join((':' + cn) for cn in column_names)) + ')'

    ret = [
        '',
        '    public function create($db, $data) {',
        '        if (! validateWrite($data)) {',
        '            return false;',
        '        }',
        '        $stmt = $db->prepare(\'' + sql.replace("'", "''") + '\');',
        '        $stmt->execute($data);',
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
        '        validateWrite($data);',
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
        '        return false;',
        '    }'
        '',
    ]

    return ret


def generate_validations(table_validations, processed_columns):
    table_validates = [
        '',
        '    private function validateTable($row) {',
        '        $ret = true;',
    ]
    read_validates = [
        '',
        '    private function validateRead($row) {',
        '        $ret = $true;',
    ]
    write_validates = [
        '',
        '    private function validateWrite($row) {',
        '        $ret = validateTable($row);',
    ]

    ret = []

    # Always run the validation, by having it appear before the '&& $ret',
    # so that the parent class can collect all of the validation errors.
    for v in processed_columns['php_read']:
        read_validates.append('        $ret = validate' + v[2] +
                              '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns['php_write']:
        write_validates.append('        $ret = validate' + v[2] +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))
    for v in processed_columns['php_validation']:
        write_validates.append('        $ret = validate' + v[2] +
                               '($row) && $ret;')
        ret.extend(generate_validation(v))

    for validation in table_validations:
        table_validates.append('        $ret = validate' +
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
        '    private function validate' + validation_name + '($row) {',
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
            cno = generate_php_name(column.name) + '_' + str(constraint.order)
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
                foreign_keys.append([
                    column.name, cn, cno + '_fk',
                    constraint.details['table'],
                    constraint.details['column']])
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
