#!/usr/bin/python3

import sys
import os
from presquel import load_package
from presquel.codegen import (AnalysisModel, filegen, php, mysql)

parent_class = None
namespace = None
output_dir = None
schema_by_name = {}

PLATFORMS = ['mysql']

# TODO this needs a large amount of improvement, so it becomes a better tool,
# much like genBaseSql.py

if __name__ == '__main__':
    (parent_class, namespace, in_dir, output_dir) = sys.argv[1:]
    package_name = os.path.basename(in_dir)
    package = load_package(in_dir, package_name)
    package_name = package.package
    head_version = package.get_newest_version()
    if head_version is None:
        print("no versions found")
        sys.exit(1)
    branch = head_version.schema_version
    if len(branch.problems) > 0:
        print("Problems discovered for " + in_dir + ":")
        for problem in branch.problems:
            print("[" + package_name + "] " + str(problem))
        sys.exit(1)

    analysis_model = AnalysisModel()
    analysis_model.add_version(branch)

    lang_gen = php.PhpLanguageGenerator()
    file_gen = filegen.FileGen(lang_gen)
    prep_sql_converter = mysql.MySqlPrepSqlConverter('php', PLATFORMS)
    for schema in branch.schema:
        config = php.PhpGenConfig(
            analysis_model.get_analysis_for(schema),
            output_dir, PLATFORMS,
            prep_sql_converter, namespace, parent_class)
        print("Generating PHP for " + config.class_name)
        file_gen.generate_file(config)
