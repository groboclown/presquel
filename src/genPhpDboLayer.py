#!/usr/bin/python3

import sys
from sqlmigration import parse_versions
from sqlmigration.codegen import (AnalysisModel, filegen, php, mysql)

parent_class = None
namespace = None
output_dir = None
schema_by_name = {}

PLATFORMS = ['mysql']

if __name__ == '__main__':
    (parent_class, namespace, in_dir, output_dir) = sys.argv[1:]
    versions = parse_versions(in_dir)
    if len(versions) <= 0:
        raise Exception("no versions found")
    head = versions[0]
    analysis_model = AnalysisModel()
    analysis_model.add_version(in_dir, head)

    lang_gen = php.PhpLanguageGenerator()
    file_gen = filegen.FileGen(lang_gen)
    prep_sql_converter = mysql.MySqlPrepSqlConverter('php', PLATFORMS)
    for schema in head.schema:
        config = php.PhpGenConfig(analysis_model.get_analysis_for(schema),
            output_dir, PLATFORMS,
            prep_sql_converter, namespace, parent_class)
        file_gen.generate_file(config)
