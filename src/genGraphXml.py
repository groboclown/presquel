#!/usr/bin/python3

import os
import sys
import presquel
import distutils.dir_util



if __name__ == '__main__':
    output_dir = sys.argv[1]
    analysis = presquel.codegen.AnalysisModel()
    for in_dir in sys.argv[2:]:
        versions = presquel.parse_versions(in_dir)
        #if len(versions) <= 0:
        #    raise Exception("no versions found")
        analysis.add_version(os.path.dirname(in_dir), versions[0])
    
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
