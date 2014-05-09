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

PLATFORMS = ['mysql']

# FIXME Analysis should use the codegen tool


def generate_file(analysis_obj):
    assert isinstance(analysis_obj, sqlmigration.codegen.ColumnSetAnalysis)

    sql_name = analysis_obj.sql_name
    class_name = generate_php_name(sql_name)
    file_name = os.path.join(output_dir, class_name + '.php')
    if os.path.exists(file_name) and FAIL_IF_EXISTS:
        raise Exception("Will not overwrite " + file_name)

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
            ' * DBO object for ' + sql_name,
            ' *',
            ' * Generated on ' + time.asctime(time.gmtime(time.time())),
            ' */',
            'class ' + class_name + ' extends ' + parent_class + ' {',
            '    public static $INSTANCE;',
            '    public $errors = array();', '',
        ])
        f.write('\n'.join(generate_read(analysis_obj)))

        if not analysis_obj.is_read_only:
            #print("Not read only: " + analysis_obj.sql_name)
            f.writelines('\n'.join(generate_create(analysis_obj)))
            # FIXME
            #f.writelines((line + '\n') for line in generate_update(
            #    analysis_obj))
            #f.writelines(line + '\n' for line in generate_delete(
            #    analysis_obj))

        # FIXME
        #f.writelines((line + '\n') for line in generate_validations(
        #    analysis_obj))

        f.write('\n'.join([
            '',
            '    private function checkForErrors($db) {',
            '        $errs = $db->errorInfo();',
            '        if ($errs[1] != null) {',
            '            $errors[] = $errs[2];',
            '        }',
            '        return false;',
            '    }', '',
            '}',
            class_name + '::$INSTANCE = new ' + class_name + ';',
            ''
        ]))


def generate_read(analysis_obj):
    assert isinstance(analysis_obj, sqlmigration.codegen.ColumnSetAnalysis)

    read_data = sqlmigration.codegen.ReadQueryData(analysis_obj, PLATFORMS)
    default_order_by = None
    always_order_by_clause = ' '
    if len(analysis_obj.primary_key_columns) == 1:
        default_order_by = analysis_obj.primary_key_columns[0]
        assert isinstance(default_order_by, sqlmigration.codegen.ColumnAnalysis)
        always_order_by_clause = ' ORDER BY '
    escaped_sql = read_data.sql.replace("'", "\\'")
    arg_names = []
    arg_arg = ''
    if len(read_data.arguments) > 0:
        arg_names = [('$' + a) for a in read_data.arguments]
        arg_arg = ', ' + ', '.join(arg_names)

    ret = [
        '',
        '    /**',
        '     * Returns the number of rows in the table.',
        '     */',
        '    public function countAll($db) {',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' +
        analysis_obj.sql_name + '\');',
        '        $stmt->execute();',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        return intval($stmt->fetchColumn());',
        '    }', ''
    ]

    # This should eventually allow for adding where clause arguments.
    ret.extend([
        '',
        '    /**',
        '     * Reads the row data without filters.',
        '     */',
        '    public function readAll($db' + arg_arg +
        ', $order = false, $start = -1, $end = -1) {',
        '        $sql = \'' + escaped_sql + always_order_by_clause + '\';',
    ])
    if len(arg_names) > 0:
        ret.append('        $data = array(')
        # Notice how this skips the use of arg_names, and recreates those values
        for a in read_data.arguments:
            ret.append('            \'' + a + '\' => $' + a + ',')
        ret.append('        );')
    else:
        ret.append('        $data = array();')
    order_code = []
    if default_order_by is not None:
        order_code.extend([
            '        if (! $order) {',
            '            $sql .= \'' + default_order_by.sql_name + '\';',
            '        } else {',
            '            $sql .= $order;',
            '        }',
        ])
    else:
        order_code.extend([
            '        if (!! $order) {',
            '            $sql .= $order;',
            '        }'
        ])
    ret.extend(order_code)
    ret.extend([
        '        if ($start >= 0 && $end > 0) {',
        '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
        '        }',
        '        $stmt = $db->prepare($sql);',
        '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
        '        $stmt->execute($data);',
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
        ''
    ])

    # TODO should we still have a generic "read" function that reads the
    # primary keys?  It's a repetition of the "readBy" methods.

    # TODO replace the "where clause" with the real where clause data structures

    ret.extend([
        '',
        '    public function countAny($db, $whereClause = false, '
        '$data = false) {',
        '        $whereClause = $whereClause || "";',
        '        $data = $data || array();',
        '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' +
        analysis_obj.sql_name + ' \'.$whereClause);',
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
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
        '        $rows = $stmt->fetchAll();',
        '        return $rows;',
        '    }',
        '',
    ])

    for read_by_columns in analysis_obj.get_selectable_column_lists():
        assert len(read_by_columns) > 0

        # FIXME if the read-by is a primary key or unique key, then the
        # order MUST NOT be part of the query, and even the start/end should
        # be removed.

        # FIXME if there are no read validations, then there shouldn't be
        # any loop-over-rows at the end.

        # each column in the column lists comes from the current table, and
        # never from a joined-to table.  So, we don't need to worry about
        # the table name as part of the column name.
        read_by_analysis = [analysis_obj.get_column_analysis(c)
                            for c in read_by_columns]
        read_by_names = [c.sql_name for c in read_by_analysis]

        title = '_x_'.join(read_by_names)
        arg_list = list(read_by_names)
        arg_list.extend(read_data.arguments)
        args = '$' + (', $'.join(arg_list))
        where_clause = read_data.where_clause
        if read_data.has_where_clauses:
            where_clause += ' AND '
        else:
            where_clause += ' WHERE '
        where_clause += (' AND '.join(((col + ' = :' + col)
                                      for col in read_by_names)))

        setup_code = ['        $data = array(']
        # Notice how this skips the use of arg_names, and recreates those values
        for a in arg_list:
            setup_code.append('            \'' + a + '\' => $' + a + ',')
        setup_code.append('        );')

        clause_sql = (read_data.from_clause + where_clause).\
            replace("'", "\\'")
        select = ('SELECT ' + read_data.select_columns_clause +
                  read_data.from_clause + where_clause).replace("'", "\\'")

        ret.extend([
            '',
            '    public function countBy_' + title + '($db, ' + args + ') {',
            '        $sql = \'SELECT COUNT(*) ' + clause_sql + '\';',
            '        $stmt = $db->prepare($sql);',
        ])
        ret.extend(setup_code)
        ret.extend([
            '        $stmt->execute(array(' + args + '));',
            '        if ($this->checkForErrors($db)) { return false; }',
            '        return $stmt->fetchColumn();',
            '    }', '' '',
            '    public function readBy_' + title + '($db, ' + args +
            ', $order = false, $start = -1, $end = -1) {',
            '        $sql = \'' + select + always_order_by_clause + '\';',
        ])
        ret.extend(setup_code)
        ret.extend(order_code)
        ret.extend([
            '        if ($start >= 0 && $end > 0) {',
            '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
            '        }',
            '        $stmt = $db->prepare($sql);',
            '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
            '        $stmt->execute($data);',
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

    return ret


def generate_create(analysis_obj):
    assert isinstance(analysis_obj, sqlmigration.codegen.ColumnSetAnalysis)
    assert not analysis_obj.is_read_only

    columns = analysis_obj.columns_for_create
    php_default_argument_list = []
    php_required_argument_list = []
    hard_coded_column_names = []
    hard_coded_column_values = []
    auto_gen_columns = []
    for c in columns:
        assert isinstance(c, sqlmigration.codegen.ColumnAnalysis)

        if c.auto_gen:
            auto_gen_columns.append(c.sql_name)

        if c.allows_create:
            arguments = c.create_arguments
            if c.default_value is not None:
                php_default_argument_list.extend(arguments)
            elif len(arguments) > 0:
                php_required_argument_list.extend(arguments)
                hard_coded_column_names.append(c.sql_name)
                if c.create_value is not None:
                    cv = c.create_value
                    assert isinstance(
                        cv, sqlmigration.model.SqlConstraint)
                    cv_sql = cv.sql
                    assert isinstance(
                        cv_sql, sqlmigration.model.SqlSet)
                    hard_coded_column_values.append(
                        cv_sql.get_for_platform(PLATFORMS))
                else:
                    # "arguments" should match the column name
                    assert len(arguments) == 1
                    hard_coded_column_values.extend(arguments)
        elif c.create_value is not None:
            # fixed initial value whose settings cannot be changed by the user
            cv = c.create_value
            assert isinstance(cv, sqlmigration.model.SqlConstraint)
            cv_sql = cv.sql
            assert isinstance(cv_sql, sqlmigration.model.SqlSet)
            hard_coded_column_names.append(c.sql_name)
            hard_coded_column_values.append(cv_sql.get_for_platform(PLATFORMS))

    php_argument_list = [('$' + a) for a in php_required_argument_list]
    php_argument_list.extend([
        ('$' + a + ' = false') for a in php_default_argument_list])

    # we can have no arguments if the table is essentially just an ID.
    php_argument_str = ''
    if len(hard_coded_column_values) > 0:
        php_argument_str = ', ' + (', '.join(php_argument_list))

    ret = [
        '',
        '    public function create($db' + php_argument_str + ') {',
        '        $sql = \'INSERT INTO ' + analysis_obj.sql_name + ' (' +
        ', '.join(hard_coded_column_names) + '\';',
        '        $values = \') VALUES (' +
        ', '.join(hard_coded_column_values) + '\';',
    ]
    if len(php_required_argument_list) <= 0:
        ret.append('        $has_columns = false;')

    ret.extend([
        '        $data = array(',
    ])

    for r in php_required_argument_list:
        ret.append('            \'' + r + '\' => $' + r)
    ret.append('        );')

    for r in php_default_argument_list:
        ret.extend([
            '        if ($' + r + ' !== false) {',
            '            $data[\'' + r + '\'] = $' + r + ';',
        ])
        if len(php_required_argument_list) <= 0:
            ret.extend([
                '            if (! $has_columns) {',
                '                $has_columns = true;',
                '            } else {',
                '                $sql .= \', \';',
                '                $values .= \', \';',
                '            }',
            ])
        ret.extend([
            '            $sql .= \'' + r + '\';',
            '            $values .= \'' + r + '\';',
            '        }',
        ])

    ret.extend([
        '        if (! $this->validateWrite($data)) {',
        '            return False;',
        '        }',
        '        $stmt = $db->prepare($sql . $values . \')\');',
        '        $stmt->execute($data);',
        '        if ($this->checkForErrors($db)) { return false; }',
    ])

    for col_name in auto_gen_columns:
        ret.extend([
            '        $id = $db->lastInsertId();',
            '        $data["' + col_name + '"] = $id;',
        ])

    ret.extend([
        '        return $data;',
        '    }',
        ''

    ])

    return ret


    # FIXME --------------------------------------------------------
    # FIXME --------------------------------------------------------
    # FIXME --------------------------------------------------------
    # FIXME --------------------------------------------------------
    # FIXME --------------------------------------------------------
    # FIXME all below here


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
    analysis_model = sqlmigration.codegen.AnalysisModel()
    analysis_model.add_version(in_dir, head)

    for schema in head.schema:
        generate_file(analysis_model.get_analysis_for(schema))
