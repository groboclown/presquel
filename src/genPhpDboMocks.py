#!/usr/bin/python3

import sys
from sqlmigration import parse_versions
from sqlmigration.codegen import (AnalysisModel, filegen, php, mysql)

parent_class = None
namespace = None
output_dir = None
schema_by_name = {}

PLATFORMS = ['mysql']

class MockPhpLanguageGenerator(php.PhpLanguageGenerator):
    def __init__(self):
        php.PhpLanguageGenerator.__init__(self)

    def generate_where_clause_classes(self, pconfig):
        """ Do nothing """
        assert isinstance(pconfig, php.PhpGenConfig)
        return []

    def _generate_invoke_init(self, pconfig, method_name):
        assert isinstance(pconfig, php.PhpGenConfig)
        assert isinstance(method_name, str)
        return [
            '        $priv_methodName = "' +
                php.escape_php_string(method_name) + '";',
            '        $priv_args = func_get_args();',
            '',
        ]

    def _generate_sql(self, indent_str = '        ',
                     stmt_var = '$stmt',
                     db_var = '$db',
                     sql_val = '$sql',
                     data_val = '$data'):
        """
        Generate the sql execute statements.
        """
        ret = [
            indent_str + stmt_var +
                ' = $db->generate($priv_methodName, $priv_args, ' + sql_val +
                ', ' + data_val + ');',
        ]
        return ret

    def generate_footer(self, pconfig):
        ret = php.PhpLanguageGenerator.generate_footer(self, pconfig)
        assert isinstance(pconfig, php.PhpGenConfig)

        ret.extend([
            pconfig.parent_class + '::$INSTANCE = new ' + pconfig.class_name +
                ';',
            ''
        ])

        return ret


if __name__ == '__main__':
    (parent_class, namespace, in_dir, output_dir) = sys.argv[1:]
    versions = parse_versions(in_dir)
    if len(versions) <= 0:
        raise Exception("no versions found")
    head = versions[0]
    analysis_model = AnalysisModel()
    analysis_model.add_version(in_dir, head)

    lang_gen = MockPhpLanguageGenerator()
    file_gen = filegen.FileGen(lang_gen)
    prep_sql_converter = mysql.MySqlPrepSqlConverter('php', PLATFORMS)
    for schema in head.schema:
        config = php.PhpGenConfig(analysis_model.get_analysis_for(schema),
            output_dir, PLATFORMS,
            prep_sql_converter, namespace, parent_class)
        config.parent_class = config.class_name
        config.class_name += 'Mock'
        file_gen.generate_file(config)
