#!/usr/bin/python

import os
import sys
import presquel


def find_max_order_len(max_len, schema_list):
    for sch in schema_list:
        if not isinstance(sch, presquel.model.SchemaObject):
            raise Exception("expected SchemaObject, found " + repr(sch)) 
        ord_len = len(str(sch.order.items()[0]))
        if ord_len > max_len:
            max_len = ord_len
        max_len = find_max_order_len(max_len, sch.sub_schema)
    return max_len


if __name__ == '__main__':
    (platform, indir, outdir) = sys.argv[1:]

    gens = presquel.get_generator(platform)
    if len(gens) <= 0:
        raise Exception("No generator found for " + platform)
    gen = gens[0]

    if not os.path.isdir(outdir):
        os.mkdir(outdir)

    versions = presquel.parse_versions(indir)
    if len(versions) <= 0:
        raise Exception("no versions found")

    version = versions[0]
    order_length = find_max_order_len(-1, version.schema)
    name_format = ('{0:0' + str(order_length) + 'd}_{1}.sql')
    for schema in version.schema:
        filename = os.path.join(outdir, name_format.format(
            schema.order.items()[0], schema.name))
        print("Generating " + filename)
        with open(filename, 'w') as f:
            for script in gen.generate_base(schema):
                f.write(script)
