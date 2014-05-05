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

        f.writelines('\n}\n')


def generate_read(schema_obj, processed_columns):
    assert (isinstance(schema_obj, sqlmigration.model.Table)
            or isinstance(schema_obj, sqlmigration.model.View))
    assert isinstance(processed_columns, ProcessedColumnSet)

    # FIXME this needs to know the foreign tables, so that it can properly
    # separate (via alias) the foreign column names.

    join = ''
    fki = 0
    # include the foreign key here, for reference
    col_names = []
    col_names.extend((schema_obj.name + '.' + col.name + ' AS ' + col.name)
                     for col in schema_obj.columns)
    for fk in processed_columns.foreign_keys:
        assert isinstance(fk, ProcessedForeignKeyConstraint)
        fki += 1
        fk_name = 'k' + str(fki)
        # Don't pick up the parent owning object in the join
        if not fk.is_owner:
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

    ret = [
        '',
        '    public function countRows($db) {',
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
        '    }', ''
    ]
    for fk in processed_columns.foreign_keys:
        assert isinstance(fk, ProcessedForeignKeyConstraint)
        if fk.is_owner:
            ret.extend([
                '',
                '    public function readFor' + fk.php_name +
                '($db, $id, $order = false, $start = -1, $end = -1) {',
                '        $sql = \'' + sql.replace("'", "''") +
                ' WHERE ' + fk.column_name + ' = ? ORDER BY \';',
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

    column_names = []
    date_cols = []
    date_vals = []
    for column in schema_obj.columns:
        if column != processed_columns.primary_key_column:
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
    values = []
    values.extend(':' + cn for cn in column_names)
    values.extend(date_vals)
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

    column_names = []
    for column in schema_obj.columns:
        if column != processed_columns.primary_key_column:
            column_names.append(column.name)
    sql = 'UPDATE ' + schema_obj.name +\
          (','.join((' SET ' + cn + ' = :' + cn) for cn in column_names)) +\
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


class ProcessedPhpValidationConstraint(AbstractProcessedConstraint):
    def __init__(self, column, constraint, validation_type, name=None):
        AbstractProcessedConstraint.__init__(self, column, constraint, name)
        self.script = constraint.details['script']
        self.order_name += '_' + validation_type


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
        for column in schema_obj.columns:
            assert isinstance(column, sqlmigration.model.Column)

            for constraint in column.constraints:
                assert isinstance(constraint,
                                  sqlmigration.model.ColumnConstraint)

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
            print("Processing " + schema.name)
            generate_file(schema, processed_column_map[schema], False)
        elif isinstance(schema, sqlmigration.model.View):
            print("View " + schema.name)
            generate_file(schema, processed_column_map[schema], True)
