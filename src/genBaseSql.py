#!/usr/bin/python

import os
import sys
import sqlmigration


def find_max_order(mo, schema_list):
    for schema in schema_list:
        if schema.order > mo:
            mo = schema.order
        mo = find_max_order(mo, schema.sub_schema)
    return mo


if __name__ == '__main__':
    (platform, indir, outdir) = sys.argv[1:]

    gens = sqlmigration.get_generator(platform)
    if len(gens) <= 0:
        raise Exception("No generator found for " + platform)
    gen = gens[0]

    if not os.path.isdir(outdir):
        os.mkdir(outdir)

    versions = sqlmigration.parse_versions(indir)
    if len(versions) <= 0:
        raise Exception("no versions found")

    version = versions[0]
    max_order = find_max_order(-1, version.schema)
    name_format = '{0:0' + str(len(str(max_order))) + 'd}_{1}.sql'
    for schema in version.schema:
        filename = os.path.join(outdir,
                                name_format.format(schema.order, schema.name))
        print("Generating " + filename)
        with open(filename, 'w') as f:
            for script in gen.generate_base(schema):
                f.write(script)
