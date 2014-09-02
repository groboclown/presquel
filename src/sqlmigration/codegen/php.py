
"""
Tools to help in the generation of PHP source files.
"""

# FIXME because of collection arguments, each SQL argument needs to be
# in BOTH the generate_code and generate_sql.  Note that only one will
# end up being used.




from .filegen import (LanguageGenerator, GenConfig)
from .converter import (PrepSqlConverter)
from .analysis import (ColumnAnalysis)
from .sql import (ReadQueryData, CreateQuery, UpdateQuery, InputValue)
from ..model.schema import (WhereClause, ExtendedSql, SqlConstraint)
from ..model.base import (SqlArgument, SqlSet, LanguageSet)
import time

def escape_php_string(php_str):
    """

    :parameter php_str: the text, as a string
    :return: escaped text, ready for insertion into a PHP string.
    """

    return (php_str.
            replace('\\', '\\\\').
            replace("'", "\\'").
            replace('"', '\\"').
            replace('\n', '\\n').
            replace('\r', '\\r').
            replace('\t', '\\t'))


def generate_php_name(schema_name):
    """
    Create a PHP style name for a schema name.

    :schema_name str:
    :return str:
    """
    first = True
    ret = ''
    for chs in schema_name:
        if chs == '_':
            first = True
        else:
            if first:
                chs = chs.upper()
                first = False
            else:
                chs = chs.lower()
            ret += chs
    assert len(ret) > 0
    return ret



class PhpGenConfig(GenConfig):
    """
    A PHP specific configuration.  It will automatically setup many computed
    values, so that it doesn't need repeating within the language generator.
    """

    def __init__(self, analysis_obj, output_dir = None, platforms = None,
            prep_sql_converter = None, namespace = None, parent_class = None):
        """
        Creates the new PHP instance of the config.
        """
        GenConfig.__init__(self, analysis_obj, output_dir, platforms,
            prep_sql_converter)

        self.namespace = namespace
        self.parent_class = parent_class
        self.sql_name = analysis_obj.sql_name
        self.class_name = generate_php_name(self.sql_name)


    def validate(self):
        GenConfig.validate(self)
        assert isinstance(self.namespace, str)
        assert isinstance(self.parent_class, str)
        assert isinstance(self.prep_sql_converter, PrepSqlConverter)


class PhpLanguageGenerator(LanguageGenerator):
    def __init__(self):
        LanguageGenerator.__init__(self)

    def generate_filename(self, config):
        assert isinstance(config, PhpGenConfig)

        return config.class_name + '.php'

    def generate_header(self, config):
        assert isinstance(config, PhpGenConfig)

        uses = ''
        if config.parent_class.count('\\') > 0:
            uses = ('use ' +
                config.parent_class[0: config.parent_class.find('\\')] +
                ';')

        ret = [
            '<?php',
            '',
            'namespace ' + config.namespace + ';',
            '',
            'use PDO;',
            uses,
            '',
        ]

        ret.extend(self.generate_where_clause_classes(config))

        ret.extend([
            '', '',
            '/**',
            ' * DBO object for ' + config.sql_name,
            ' *',
            ' * Generated on ' + time.asctime(time.gmtime(time.time())),
            ' */',
            'class ' + config.class_name + ' extends ' + config.parent_class +
                ' {',
            '    public static $INSTANCE;',
            '',
        ])

        return ret

    def generate_where_clause_classes(self, config):
        assert isinstance(config, PhpGenConfig)

        # In PHP, the where clause classes live outside the class definition,
        # so we create them in the file header.
        ret = []
        if len(config.analysis_obj.schema.where_clauses) > 0:
            ret.extend([
                '', '',
                'class ' + config.class_name + '__WhereParent {',
                '    public function bindVariables(&$data) {}',
                '}',
                '', ''
            ])

            for whc in config.analysis_obj.schema.where_clauses:
                assert isinstance(whc, WhereClause)
                sql = whc.sql
                assert isinstance(sql, SqlSet)

                ret.extend([
                    '', '',
                    '/**',
                    ' * Where clause for ' + config.sql_name,
                    ' */',
                    'class ' + config.class_name + '_' +
                        generate_php_name(whc.name) +
                    ' extends ' + config.class_name + '__WhereParent {',
                    ''
                ])

                if len(sql.arguments) > 0:
                    for arg in sql.arguments:
                        ret.append('    public $' + arg.name + ';')
                    ret.append('    function __construct(' +
                        (', '.join(('$' + arg.name) for arg in sql.arguments)) +
                        ') {')
                    for arg in sql.arguments:
                        ret.append('        $this->' + arg.name + ' = $' +
                            arg.name + ';')
                    ret.append('    }')

                ret.extend([
                    '', '',
                    '    public function bindVariables(&$data) {',
                    '',
                ])

                # FIXME allow for code.
                for arg in sql.arguments:
                    ret.append('        $data["' + arg.name + '"] = $this->' +
                        arg.name + ';')
                ret.extend([
                    '    }', '', ''
                    '    public function __toString() {',
                    '        return "' + escape_php_string(
                        config.prep_sql_converter.generate_sql(sql)) + '";',
                    '    }', '',
                    '}', ''
                ])
        return ret

    def generate_read(self, config):
        assert isinstance(config, PhpGenConfig)

        read_data = ReadQueryData(config.analysis_obj, config.platforms, 'php')
        default_order_by = None
        always_order_by_clause = ' '
        if len(config.analysis_obj.primary_key_columns) == 1:
            default_order_by = config.analysis_obj.primary_key_columns[0]
            assert isinstance(default_order_by, ColumnAnalysis)
            always_order_by_clause = ' ORDER BY '
        escaped_sql = escape_php_string(read_data.sql)
        arg_names = []
        arg_arg = ''
        if len(read_data.arguments) > 0:
            arg_names = [('$' + a) for a in read_data.arguments]
            arg_arg = ', ' + ', '.join(arg_names)

        where_arg = ''
        if len(config.analysis_obj.schema.where_clauses) > 0:
            where_arg = ', $whereClauses = null'

        ret = [
            '',
            '    /**',
            '     * Returns the number of rows in the table.',
            '     */',
            '    public function countAll($db' + where_arg + ') {',
            '        $sql = \'SELECT COUNT(*) FROM ' + config.sql_name +
            '\';',
            '        $data = array();',
        ]
        ret.extend(PhpLanguageGenerator._generate_where_clause(
               config.analysis_obj, False))
        ret.extend(self._generate_sql())
        ret.extend([
            '        return $this->createReturn($stmt, function ($s) {',
            '            return intval($s->fetchColumn());',
            '        });',
            '    }', ''
        ])

        ret.extend([
            '',
            '    /**',
            '     * Reads the row data without filters.',
            '     */',
            '    public function readAll($db' + arg_arg + where_arg +
            ', $order = false, $start = -1, $end = -1) {',
            '        $sql = \'' + escaped_sql + '\';',
        ])
        if len(arg_names) > 0:
            ret.append('        $data = array(')
            # Notice how this skips the use of arg_names, and recreates those values
            for a in read_data.arguments:
                ret.append('            \'' + a + '\' => $' + a + ',')
            ret.append('        );')
        else:
            ret.append('        $data = array();')
        if len(config.analysis_obj.schema.where_clauses) > 0:
            ret.extend(PhpLanguageGenerator._generate_where_clause(
                config.analysis_obj, False))
        ret.append('        $sql .= \'' + always_order_by_clause + '\';')
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
                '            $sql .= " ORDER BY " . $order;',
                '        }'
            ])
        ret.extend(order_code)
        ret.extend([
            '        if ($start >= 0 && $end > 0) {',
            '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
            '        }'
        ])
        ret.extend(self._generate_sql())
        ret.append('        return $this->createReturn($stmt, function ($s) {')
        if len(config.analysis_obj.get_read_validations()) > 0:
            # TODO add the invalid rows to a "invalidrows" array in the return
            # structure.
            ret.extend([
                '            $rows = array();',
                '            foreach ($s->fetchAll() as $row) {',
                '                if (!$this->validateRead($row)) {',
                '                    return null;',
                '                }',
                '                $rows[] = $row;',
                '            }',
                '            return $rows;'
            ])
        else:
            ret.extend([
                '            return $s->fetchAll();',
            ])
        ret.extend([
            '        });',
            '    }', '',
        ])


        # NOTE: no where clause object support for the "any"
        ret.extend([
            '',
            '    public function countAny($db, $whereClause = false, '
            '$data = false) {',
            '        $whereClause = $whereClause || "";',
            '        $data = $data || array();',
            '        $stmt = $db->prepare(\'SELECT COUNT(*) FROM ' +
            config.sql_name + ' \'.$whereClause);',
            '        $stmt->execute($data);',
            '        return $this->createReturn($stmt, function ($s) {',
            '            return intval($s->fetchColumn());',
            '        });',
            '    }', '', '',
            '    public function readAny($db, $query, $data, $start = -1, '
            '$end = -1) {',
            '        if ($start >= 0 && $end > 0) {',
            '            $query .= \' LIMIT \'.$start.\',\'.$end;',
            '        }'
        ])
        ret.extend(self._generate_sql(sql_val = '$query'))
        ret.extend([
            # No validation can be performed with the results, because we don't
            # know what's in the results.
            '        return $this->createReturn($stmt, function ($s) {',
            '            return $s->fetchAll();',
            '        });',
            '    }',
            '',
        ])

        for readby_columns in config.analysis_obj.get_selectable_column_lists():
            assert len(readby_columns) > 0

            # TODO if the read-by is a primary key or unique key, then the
            # order MUST NOT be part of the query, and even the start/end should
            # be removed.

            # each column in the column lists comes from the current table, and
            # never from a joined-to table.  So, we don't need to worry about
            # the table name as part of the column name.

            read_by_analysis = [config.analysis_obj.get_column_analysis(c)
                                for c in readby_columns]
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
            # Notice how this skips the use of arg_names, and recreates those
            # values
            for arg in arg_list:
                setup_code.append('            \'' + arg + '\' => $' + arg +
                                  ',')
            setup_code.append('        );')

            clause_sql = escape_php_string(read_data.from_clause + where_clause)
            select = escape_php_string('SELECT ' +
                         read_data.select_columns_clause +
                         read_data.from_clause + where_clause)

            ret.extend([
                '',
                '    public function countBy_' + title + '($db, ' + args +
                where_arg + ') {',
                '        $sql = \'SELECT COUNT(*) ' + clause_sql + '\';',
            ])
            ret.extend(setup_code)
            ret.extend(PhpLanguageGenerator._generate_where_clause(
                config.analysis_obj, True))
            ret.extend(self._generate_sql())
            ret.extend([
                '        return $this->createReturn($stmt, function ($s) {',
                '            return intval($s->fetchColumn());',
                '        });',
                '    }', '' '',
                '    public function readBy_' + title + '($db, ' + args +
                where_arg + ', $order = false, $start = -1, $end = -1) {',
                '        $sql = \'' + select + '\';',
            ])
            ret.extend(setup_code)
            ret.extend(PhpLanguageGenerator._generate_where_clause(
                config.analysis_obj, True))
            ret.append('        $sql .= \'' + always_order_by_clause + '\';')
            ret.extend(order_code)
            ret.extend([
                '        if ($start >= 0 && $end > 0) {',
                '            $sql .= \' LIMIT \'.$start.\',\'.$end;',
                '        }'
            ])
            ret.extend(self._generate_sql())
            ret.append(
                '        return $this->createReturn($stmt, function ($s) {')

            if len(config.analysis_obj.get_read_validations()) > 0:
                ret.extend([
                    '            $rows = array();',
                    '            foreach ($s->fetchAll() as $row) {',
                    '                if (!$this->validateRead($row)) {',
                    '                    return null;',
                    '                }',
                    '                $rows[] = $row;',
                    '            }',
                    '            return $rows',
                ])
            else:
                ret.extend([
                    '            return $s->fetchAll();',
                ])

            ret.extend([
                '        });',
                '    }', '',
            ])

        return ret

    def generate_create(self, config):
        assert isinstance(config, PhpGenConfig)
        assert not config.analysis_obj.is_read_only

        create = CreateQuery(config.analysis_obj)

        php_argument_list = [('$' + arg)
            for arg in create.required_input_arguments]
        php_argument_list.extend([('$' + arg + ' = false')
            for arg in create.optional_input_arguments])

        # we can have no arguments if the table is essentially just an ID.
        php_argument_str = ''
        if len(php_argument_list) > 0:
            php_argument_str = ', ' + (', '.join(php_argument_list))

        ret = [
            '',
            '    public function create($db' + php_argument_str + ') {',
            '        $columns = array();',
            '        $values = array();',
            '        $data = array();',
        ]

        for arg in create.required_input_values:
            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, True)
            ret.append('        $columns[] = "' +
                escape_php_string(arg.column_name) + '";')
            if php_code is not None:
                ret.extend(php_code)
                ret.append('        $values[] = $tmpSql;')
            else:
                ret.append('        $values[] = "' +
                    escape_php_string(sql_value) + '";')

            for anx in create.value_arguments[arg]:
                ret.append('        $data["' + anx.name +
                    '"] = $' + anx.name + ';')

        for arg in create.optional_input_values:
            optional_arg = []
            for var in create.value_arguments[arg]:
                if var.name in create.optional_input_arguments:
                    optional_arg.append(var.name)
            ret.extend([
                '        if (' + (' && '.join(('$' + var + ' !== false')
                    for var in optional_arg)) + ') {',
                '            $columns[] = "' +
                    escape_php_string(arg.column_name) + '";'
            ])

            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, True)
            if php_code is not None:
                ret.extend(php_code)
                ret.append('            $values[] = $tmpSql;')
            else:
                ret.append('            $values[] = "' +
                    escape_php_string(sql_value) + '";')

            for anx in create.value_arguments[arg]:
                ret.append('            $data["' + anx.name +
                    '"] = $' + anx.name + ';')

            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, False)
            if php_code is not None or sql_key is not None:
                ret.extend(['        } else {'
                    '            $columns[] = "' +
                        escape_php_string(arg.column_name) + '";'
                    ])
                if php_code is not None:
                    ret.extend(php_code)
                    ret.append('            $values[] = $tmpSql;')
                else:
                    ret.append('            $values[] = "' +
                        escape_php_string(sql_value) + '";')

                for argv in [ arg.get_code(False), arg.get_sql(False) ]:
                    for argx in argv.arguments:
                        ret.append('            $data["' + argx.name +
                            '"] = $' + argx.name + ';')

            ret.append('        }')

        # FIXME This "where" doesn't really work right, and it doesn't look like it
        # will ever really work right (for MySql anyway).
        # has_where = len(create.where_values) > 0
        # if has_where:
        #    ret.append('        $where = " FROM ' + analysis_obj.sql_name +
        #               ' WHERE 1 = 1";')
        #    for wr in create.where_values[r]:
        #        assert isinstance(wr, InputValue)
        #        code = wr.get_code_value(True)
        #        if code is not None:
        #            ret.append(code)
        #        for arg in wr.get_sql_arguments(True):
        #            assert isinstance(arg, sqlmigration.model.SqlArgument)
        #            data_values.append('            \'' + arg.name +
        #                '\' => $' + arg.name + ',')
        #        ret.append('        $where .= \' AND ' + wr.get_sql_value(True) +
        #                   '\';')
        #        # Also for the optional values....
        # This would change the construction of the insert statement into one
        # that includes a sub-select.

        ret.extend([
            '        if (! $this->validateWrite($data)) {',
            '            return false;',
            '        }',
            '        $sql = "INSERT INTO ' + escape_php_string(
                config.sql_name) +
            ' (".join(", ", $columns).") VALUES (".join(", ", $values).")";'
        ])
        ret.extend(self._generate_sql())
        ret.extend([
            '        $ret = $this->createReturn($stmt, function ($s) {',
            '            return true;',
            '        });',
        ])

        if create.generated_column_name is not None:
            ret.append('        $ret["result"] = $db->lastInsertId();')

        ret.extend([
            '        return $ret;',
            '    }', ''
        ])


        # -------------------------------------------------------------------
        # Create the upsert command (insert or update if exists)
        # We should only generate this if:
        #   - there is no autoincrement column
        #   - there is a unique index or primary key
        # We should also generate this for each primary key / unique index.


        primary_keys = config.analysis_obj.primary_key_columns
        allow_upsert = len(primary_keys) > 0
        for pkey in primary_keys:
            assert isinstance(pkey, ColumnAnalysis)
            if pkey.auto_gen:
                allow_upsert = False
            else:
                if php_argument_list.count('$' + pkey.sql_name) > 0:
                    php_argument_list.remove('$' + pkey.sql_name)
        allow_upsert = allow_upsert and len(php_argument_list) > 0

        if allow_upsert:
            # print("non index required columns: " +
            #    repr(non_index_required_columns))
            update_values = {}
            for cfu in config.analysis_obj.columns_for_update:
                assert isinstance(cfu, ColumnAnalysis)
                cuv = cfu.update_value
                if cuv is not None:
                    cuvc = cuv.constraint
                    # TODO in the future, this might be code
                    assert isinstance(cuvc, SqlConstraint)
                    update_values[cfu.sql_name] = (
                        config.prep_sql_converter.generate_sql(cuvc))
                else:
                    update_values[cfu.sql_name] = (
                        config.prep_sql_converter.generate_sql(
                            cfu.name_as_sql_argument))

            ret.extend([
                '',
                '    public function upsert($db, $' +
                (', $'.join(c.sql_name for c in primary_keys)) + ', ' +
                (', '.join(php_argument_list)) +
                ') {',
                '        $columns = array();',
                '        $values = array();',
                '        $dups = array();',
                '        $data = array();'
            ])

            for pkey in primary_keys:
                # Primary key columns are always (!) straight values.
                # If they aren't, then the user did something wrong.
                assert isinstance(pkey, ColumnAnalysis)
                val = InputValue.create_direct_value(pkey, True, False)
                val_sql = config.prep_sql_converter.generate_sql(
                    val.get_sql(True))
                ret.extend([
                    '        $columns[] = "' +
                        escape_php_string(pkey.sql_name) + '";',
                    '        $values[] = "' +
                        escape_php_string(val_sql) + '";',
                    '        $data["' + escape_php_string(pkey.sql_name) +
                        '"] = $' + pkey.sql_name + ';'
                ])

            # This required + optional values are really close to the above
            # code, but are slightly different.
            for arg in create.required_input_values:
                assert isinstance(arg, InputValue)
                # don't re-add the primary key columns here
                if arg.column in primary_keys:
                    # Remember the comment above about the user doing something
                    # wrong with primary keys?  This is where we check that
                    # the user did it right.
                    if (len(create.value_arguments[arg]) != 1 or
                            not isinstance(
                                create.value_arguments[arg][0], SqlArgument)):
                        raise Exception("primary key columns cannot be complex")
                    continue

                php_code, sql_key, sql_value = (
                    PhpLanguageGenerator._convert_arg(config, arg, True))
                ret.append('        $columns[] = "' +
                    escape_php_string(arg.column_name) + '";')
                if php_code is not None:
                    ret.extend(php_code)
                    ret.append('        $values[] = $tmpSql;')
                    ret.append('        $dups[] = "' +
                        escape_php_string(arg.column_name + ' = ') +
                        '".$tmpSql;')
                else:
                    ret.append('        $values[] = "' +
                        escape_php_string(sql_value) + '";')
                    ret.append('        $dups[] = "' +
                        escape_php_string(arg.column_name + ' = ' +
                            sql_value) + '";')

                for anx in create.value_arguments[arg]:
                    ret.append('        $data["' + anx.name +
                        '"] = $' + anx.name + ';')

            for arg in create.optional_input_values:
                optional_arg = []
                for var in create.value_arguments[arg]:
                    if var.name in create.optional_input_arguments:
                        optional_arg.append(var.name)
                ret.extend([
                    '        if (' + (' && '.join(('$' + var + ' !== false')
                        for var in optional_arg)) + ') {',
                    '            $columns[] = "' +
                        escape_php_string(arg.column_name) + '";'
                ])

                php_code, sql_key, sql_value = (
                    PhpLanguageGenerator._convert_arg(config, arg, True))
                if php_code is not None:
                    ret.extend(php_code)
                    ret.append('            $values[] = $tmpSql;')
                    ret.append('            $dups[] = "' +
                        escape_php_string(arg.column_name + ' = ') +
                        '".$tmpSql;')
                else:
                    ret.append('            $values[] = "' +
                        escape_php_string(sql_value) + '";')
                    ret.append('            $dups[] = "' +
                        escape_php_string(arg.column_name + ' = ' +
                            sql_value) + '";')

                for anx in create.value_arguments[arg]:
                    ret.append('            $data["' + anx.name +
                        '"] = $' + anx.name + ';')

                php_code, sql_key, sql_value = (
                    PhpLanguageGenerator._convert_arg(config, arg, False))
                if php_code is not None or sql_key is not None:
                    ret.extend(['        } else {'
                        '            $columns[] = "' +
                            escape_php_string(arg.column_name) + '";'
                        ])

                    if php_code is not None:
                        ret.extend(php_code)
                        ret.append('            $values[] = $tmpSql;')
                        ret.append('            $dups[] = "' +
                            escape_php_string(arg.column_name + ' = ') +
                            '".$tmpSql;')
                    else:
                        ret.append('            $values[] = "' +
                            escape_php_string(sql_value) + '";')
                        ret.append('            $dups[] = "' +
                            escape_php_string(arg.column_name + ' = ' +
                                sql_value) + '";')

                    for argv in [ arg.get_code(False), arg.get_sql(False) ]:
                        for argx in argv.arguments:
                            ret.append('            $data["' + argx.name +
                                '"] = $' + argx.name + ';')

                ret.append('        }')

            ret.extend([
                '        if (! $this->validateWrite($data)) {',
                '            return false;',
                '        }',
            ])

            ret.extend([
                '        $sql = "' + escape_php_string('INSERT INTO ' +
                    config.sql_name + ' (') + '".join(", ", $columns)."' +
                    escape_php_string(') VALUES (') +
                    '".join(", ", $values)."' + escape_php_string(
                    ') ON DUPLICATE KEY UPDATE ') + '".join(", ", $dups);'
            ])

            ret.extend(self._generate_sql())

            ret.extend([
                '        $ret = $this->createReturn($stmt, function ($s) {',
                '            return true;',
                '        });',
                '    }', ''
            ])


        return ret

    def generate_update(self, config):
        assert isinstance(config, PhpGenConfig)

        update = UpdateQuery(config.analysis_obj)

        if (len(update.required_input_arguments) +
                len(update.optional_input_arguments)) <= 0:
            # Nothing to do
            print("NOTICE: " + config.class_name +
                " - No input arguments.  No update!")
            return []

        if len(update.primary_key_columns) <= 0:
            # Nothing to do again
            print("NOTICE: " + config.class_name +
                  " - No primary key. No update!")
            return []

        req_pair_strs = {}
        req_pair_code = []

        # Load up the required pairs.
        # TODO This generated php could be better optimized by
        # directly loading the sql-only bits into the original string.
        for arg in update.required_input_values:
            assert isinstance(arg, InputValue)
            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, True)
            if php_code is not None:
                req_pair_code.extend(php_code)
                req_pair_code.append('        $pairs[] = "' +
                    escape_php_string(arg.column_name) + ' = $tmpSql;')
            else:
                req_pair_strs[sql_key] = sql_value

        php_arguments = [
             ('$' + arg.column_name)
             for arg in update.primary_key_values
        ]
        php_arguments.extend([
             ('$' + arg)
             for arg in update.required_input_arguments
        ])
        php_arguments.extend([
             ('$' + arg + ' = false')
             for arg in update.optional_input_arguments
        ])

        ret = [
            '',
            '    public function update($db, ' + ', '.join(php_arguments) +
                ') {',
            '        $sql = "' + escape_php_string('UPDATE ' +
                config.sql_name + ' SET ') + '";',
            '        $pairs = array(',
        ]

        # Required values
        for col, sql in req_pair_strs.items():
            ret.append('            "' + escape_php_string(col) + ' = ' +
                escape_php_string(sql) + '",')
        ret.append('        );')
        ret.extend(req_pair_code)

        ret.append('        $data = array(')
        for arg in update.required_input_arguments:
            ret.extend([
                '            "' + arg + '" => $' + arg + ',',
            ])
        ret.extend([
            '        );',
        ])

        # Optional values
        for arg in update.optional_input_values:
            assert isinstance(arg, InputValue)

            optional_arg = []
            for var in update.value_arguments[arg]:
                if var.name in update.optional_input_arguments:
                    optional_arg.append(var.name)
            ret.append('        if (' + (
                ' && '.join(('$' + var + ' !== false')
                    for var in optional_arg)) + ') {')

            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, True)
            if php_code is not None:
                ret.extend(php_code)
                ret.append('        $pairs[] = "' +
                    escape_php_string(arg.column_name) + ' = " . $tmpSql;')
            else:
                ret.append('            $pairs[] = "' +
                    escape_php_string(sql_key) +
                    ' = ' + escape_php_string(sql_value) + '";')

            for anx in update.value_arguments[arg]:
                ret.append('            $data["' + anx.name +
                    '"] = $' + anx.name + ';')

            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, arg, False)
            if php_code is not None or sql_key is not None:
                ret.append('        } else {')
                if php_code is not None:
                    ret.extend(php_code)
                    ret.append('        $pairs[] = "' +
                        escape_php_string(arg.column_name) + ' = " . $tmpSql;')
                else:
                    ret.append('            $pairs[] = "' +
                        escape_php_string(sql_key) +
                        ' = ' + escape_php_string(sql_value) + '";')

                for argv in [ arg.get_code(False), arg.get_sql(False) ]:
                    for argx in argv.arguments:
                        ret.append('            $data["' + argx.name +
                            '"] = $' + argx.name + ';')

            ret.append('        }')

        # Updates must ALWAYS have a where clause.
        ret.extend([
            '        $sql .= join(", ", $pairs) . " WHERE ";',
            '        $pairs = array('
        ])

        # Where clause
        where_ands = []
        where_ands_code = []
        where_data = []
        for val in update.where_values:
            # FIXME for now, we assume that all these where clauses are
            # required.

            assert isinstance(val, InputValue)
            php_code, sql_key, sql_value = PhpLanguageGenerator._convert_arg(
                config, val, True)
            if php_code is not None:
                # Note that we require the PHP code AND the sql to both be
                # in the correct where-clause form (a = b or whichever is
                # required)
                where_ands_code.extend(php_code)
                where_ands_code.extend('        $pairs[] = $tmpSql;')
            else:
                where_ands.append('"' + escape_php_string(sql_value) + '"')
            for arg_list in [ val.get_code(True), val.get_sql(True) ]:
                if arg_list is not None:
                    for arg in arg_list.arguments:
                        where_data.append('        $data["' +
                              escape_php_string(arg.name) +
                              '"] = $' + arg.name + ';')

        for wand in where_ands:
            ret.append('            ' + wand + ',')
        ret.append('        );')
        ret.extend(where_ands_code)
        ret.extend(where_data)
        ret.append('        $sql .= join(" AND ", $pairs);')

        # FIXME check if updated row count was 0, and if so report an error.
        ret.extend([
            '        $stmt = $db->prepare($sql);',
            '        $stmt->execute($data);',
            '        return $this->createReturn($stmt, function ($s) {',
            '            return true;',
            '        });',
            '    }', ''
        ])

        return ret

    def generate_delete(self, config):
        assert isinstance(config, PhpGenConfig)

        args = [('$' + col.sql_name)
            for col in config.analysis_obj.primary_key_columns
        ]
        if len(args) <= 0:
            print("** WARNING: no way to delete " +
                  config.analysis_obj.sql_name)
            return []

        # FIXME change this to use the converter
        sql = escape_php_string('DELETE FROM ' + config.analysis_obj.sql_name +
            ' WHERE ' + ' AND '.join([
                (col.sql_name + ' = :' + col.sql_name)
                for col in config.analysis_obj.primary_key_columns
            ]))

        ret = [
            '',
            '    public function remove($db, ' + ', '.join(args) + ') {',
            '        $data = array(',
        ]

        for col in config.analysis_obj.primary_key_columns:
            ret.append('            "' + col.sql_name + '" => $' +
                col.sql_name + ',')
        ret.append('        );')

        ret.extend(self._generate_sql(sql_val = '"' + sql + '"'))

        ret.extend([
            '        return $this->createReturn($stmt, function ($s) {',
            '            return true;',
            '        });',
            '    }'
            '',
        ])

        return ret

    def generate_extended_sql(self, config, extended_sql):
        assert isinstance(config, PhpGenConfig)
        assert isinstance(extended_sql, ExtendedSql)
        assert not extended_sql.is_wrapper

        php_name = generate_php_name(extended_sql.name)
        arg_prefix = ''
        if len(extended_sql.arguments) > 0:
            arg_prefix = ', '

        ret = [
            '',
            '    public function run' + php_name + '($db' + arg_prefix +
                (', '.join(('$' + arg.name)
                    for arg in extended_sql.arguments)) +
                ', $start = -1, $end = -1) {',
            '        $sql = "' + escape_php_string(
                config.prep_sql_converter.generate_sql(extended_sql.sql)) +
                '";',
            '        if ($start >= 0 && $end > 0) {',
            '            $sql .= " LIMIT ".$start.", ".$end;',
            '        }',
            '        $data = array(',
        ]

        for arg in extended_sql.arguments:
            assert isinstance(arg, SqlArgument)
            ret.append('            "' + arg.name + '" => $' + arg.name + ',')

        ret.extend([
            '        );',
            '        $stmt = $db->prepare($sql);',
            '        $stmt->setFetchMode(PDO::FETCH_ASSOC);',
            '        $stmt->execute($data);',
            # No validation can be performed with the results, because we don't
            # know what's in the results.
            '        return $this->createReturn($stmt, function ($s) {',
        ])
        if extended_sql.sql_type == 'query':
            ret.append('            return $s->fetchAll();')
        elif extended_sql.sql_type in ['id', 'count']:
            ret.append('            return intval($s->fetchColumn);')
        else:
            ret.append('            return true;')
        ret.extend([
            '        });',
            '    }', '', '',
        ])

        return ret

    def generate_extended_sql_wrapper(self, config, extended_sql):
        assert isinstance(config, PhpGenConfig)
        assert isinstance(extended_sql, ExtendedSql)
        assert extended_sql.is_wrapper

        php_name = generate_php_name(extended_sql.name)
        arg_prefix = ''
        if len(extended_sql.arguments) > 0:
            arg_prefix = ', '
        funcdecl_str = (php_name + '($db' + arg_prefix +
            (', '.join(('$' + a.name) for a in extended_sql.arguments)))

        ret = [
            '',
            '    public function wrap' + funcdecl_str +
                ', $invoker_arg, $invoker) {',
            '        $data = array(',
        ]
        for arg in extended_sql.arguments:
            assert isinstance(arg, SqlArgument)
            ret.append('            "' + arg.name + '" => $' + arg.name + ',')
        ret.append("        );")
        ret.append('        $sql = "' + escape_php_string(
            config.prep_sql_converter.generate_sql(extended_sql.sql)) +
            '";')
        ret.extend(self._generate_sql())
        ret.extend([
            '        $errs = $stmt->errorInfo();',
            '        if ($errs[1] !== null) {',
            '            return $this->createReturn($stmt, null);',
            '        }',
            '        $except = null;',
            '        $ret = null;',
            '        try {',
            '            $ret = $invoker($db, $invoker_arg);',
            '        } catch (Exception $e) {',
            '            $except = $e;',
            '        }',
            '        $sql = "' + escape_php_string(
                config.prep_sql_converter.generate_sql(extended_sql.post_sql)) +
                '";'
        ])
        ret.extend(self._generate_sql())
        ret.extend([
            '        $errs = $stmt->errorInfo();',
            # Regardless of whether the unlock caused an error or not, use
            # the top-level invoker error as the return, if it had an error.
            '        if ($except !== null) {',
            '            throw $except;',
            '        }',
            '        if ($ret !== null && $ret["haserror"]) {',
            '            return $ret;',
            '        }',
            # IF there was an error only in the unocking, then return that as
            # the error.
            '        if ($errs[1] !== null) {',
            '            return $this->createReturn($stmt, null);',
            '        }',
            '        return $ret;',
            '    }', '', '',
            ])

        return ret

    def generate_validations(self, config):
        assert isinstance(config, PhpGenConfig)

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

        # FIXME --------------------------------------------------------
        # FIXME --------------------------------------------------------
        # FIXME --------------------------------------------------------
        # FIXME --------------------------------------------------------
        # FIXME --------------------------------------------------------
        # FIXME these comments and what they call need to be redone

        # for v in processed_columns.php_read:
        #    assert isinstance(v, ProcessedPhpValidationConstraint)
        #    read_validates.append('        $ret = $this->validate' + v.order_name +
        #                          '($row) && $ret;')
        #    ret.extend(generate_validation(v))
        # for v in processed_columns.php_write:
        #    assert isinstance(v, ProcessedPhpValidationConstraint)
        #    write_validates.append('        $ret = $this->validate' + v.order_name +
        #                           '($row) && $ret;')
        #    ret.extend(generate_validation(v))
        # for v in processed_columns.php_validation:
        #    assert isinstance(v, ProcessedPhpValidationConstraint)
        #    write_validates.append('        $ret = $this->validate' + v.order_name +
        #                           '($row) && $ret;')
        #    ret.extend(generate_validation(v))
        #
        # for validation in table_validations:
        #    assert isinstance(validation, ProcessedPhpValidationConstraint)
        #    table_validates.append('        $ret = $this->validate' +
        #                           validation.order_name + '($row) && $ret;')
        #    ret.extend(generate_validation(validation))

        table_validates.extend([
            '        return $this->finalCheck($ret);', '    }',
            ''
        ])
        read_validates.extend([
            '        return $this->finalCheck($ret);', '    }',
            ''
        ])
        write_validates.extend([
            '        return $this->finalCheck($ret);', '    }',
            ''
        ])
        ret.extend(read_validates)
        ret.extend(write_validates)
        ret.extend(table_validates)

        return ret

    def generate_footer(self, config):
        assert isinstance(config, PhpGenConfig)

        ret = [
            '',
            '    private function createReturn($stmt, $extractor) {',
            '        $errs = $stmt->errorInfo();',
            '        $ret = array("haserror" => false, "rowcount" => 0, ' +
            '"success" => true, "result" => null);',
            '        if ($errs[1] !== null) {',
            '            $ret["haserror"] = true;',
            '            $ret["success"] = false;',
            '            $ret["error"] = $errs[2];',
            '            $ret["errorcode"] = $errs[1];',
            '        } else {',
            '            $ret["rowcount"] = $stmt->rowCount();',
            '            $ret["result"] = $extractor($stmt);',
            '        }',
            # FIXME is there a close statement to run?
            '        //$stmt->close();',
            '        return $ret;',
            '    }', '',
            '}',
            config.class_name + '::$INSTANCE = new ' + config.class_name + ';',
            ''
        ]
        return ret


    def _generate_sql(self, indent_str = '        ',
                     stmt_var = '$stmt',
                     db_var = '$db',
                     sql_val = '$sql',
                     data_val = '$data'):
        """
        Generate the sql execute statements.
        """
        ret = [
            indent_str + stmt_var + ' = ' + db_var + '->prepare(' + sql_val +
                ');',
            indent_str + stmt_var + '->setFetchMode(PDO::FETCH_ASSOC);',
            indent_str + stmt_var + '->execute(' + data_val + ');'
        ]
        return ret


    @staticmethod
    def _generate_where_clause(analysis_obj, already_added_where):
        """
        Generate the sql where clause based on the where clause classes.
        """
        ret = []
        if len(analysis_obj.schema.where_clauses) > 0:
            ret.append(
                '        if ($whereClauses !== null && sizeof($whereClauses) > 0) {')
            if already_added_where:
                ret.extend([
                '            foreach ($whereClauses as $w) {',
                '                $w->bindVariables($data);',
                '                $sql .= " AND " . $w;',
                '            }',
                ])
            else:
                ret.extend([
                    '            $where = " WHERE ";',
                    '            foreach ($whereClauses as $w) {',
                    '                $w->bindVariables($data);',
                    '                $sql .= $where . $w;',
                    '                $where = " AND ";',
                    '            }',
                ])
            ret.append('        }')
        return ret

    @staticmethod
    def _convert_arg(config, arg, is_required):
        assert isinstance(config, PhpGenConfig)
        assert isinstance(arg, InputValue)
        assert isinstance(is_required, bool)
        sql_key = None
        sql_value = None
        php_code = None

        code = arg.get_code(is_required)
        if code is not None:
            # We need to construct the wrapper code.
            assert isinstance(code, LanguageSet)
            php_code = [
                config.prep_sql_converter.generate_code('$tmpSql', code),
            ]
        else:
            sql = arg.get_sql(is_required)
            if sql is not None:
                assert isinstance(sql, SqlSet)
                sql_key = arg.column_name
                sql_value = config.prep_sql_converter.generate_sql(sql)

        return (php_code, sql_key, sql_value)
