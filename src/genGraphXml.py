#!/usr/bin/python3

import os
import sys
import presquel
import distutils.dir_util



if __name__ == '__main__':
    output_dir = sys.argv[1]
    analysis = presquel.codegen.AnalysisModel()
    for in_dir in sys.argv[2:]:
        package = presquel.load_package(in_dir)
        head_version = package.get_newest_version()
        if head_version is None:
            print("no versions found in {0}".format(in_dir))
            sys.exit(1)
        branch = head_version.schema_version
        if len(branch.problems) > 0:
            print("Problems discovered for {0}:".format(in_dir))
            for problem in branch.problems:
                print("[{0}] {1}".format(package_name, problem))
            sys.exit(1)

        analysis.add_version(branch)

    xml = presquel.codegen.generate_graph_xml(analysis)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    distutils.dir_util.copy_tree(
         os.path.join('..', 'ui'),
         output_dir,
         preserve_symlinks = False,
         update = True,
         verbose = True,
         dry_run = False)
    with open(os.path.join(output_dir, 'schema.graph.xml'), 'wb') as f:
        f.write(xml)
