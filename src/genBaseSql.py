#!/usr/bin/python

import os
import sys
import presquel
import argparse


VERSION = "%{prog}s " + presquel.VERSION_STR


def find_max_order_len(max_len, schema_list):
    for sch in schema_list:
        if not isinstance(sch, presquel.model.SchemaObject):
            raise Exception("expected SchemaObject, found " + repr(sch)) 
        ord_len = len(str(sch.order.items()[0]))
        if ord_len > max_len:
            max_len = ord_len
        max_len = find_max_order_len(max_len, sch.sub_schema)
    return max_len


class SourceSetup(object):
    def __init__(self, base_dir: str):
        self.problems = []

        version_split = base_dir.split("@")
        if len(version_split) == 1:
            self.base_dir = base_dir
            self.version_name = None
        elif len(version_split) == 2:
            self.base_dir = version_split[0]
            self.version_name = version_split[1]
        else:
            self.problems.append(
                "invalid version definition: '" + base_dir + "'")
            return

        self.package_name = os.path.basename(self.base_dir)

        if not os.path.isdir(self.base_dir):
            self.problems.append("not a directory: " + self.base_dir)

        self.out_dir = None
        self.package = None
        self.branch = None

    def load(self):
        self.package = presquel.load_package(self.base_dir, self.package_name)
        for number in self.package.unresolved_branch_versions:
            self.problems.append(
                "package references unknown version number " + str(number))
        self.package_name = self.package.package

        if self.version_name is None:
            self.branch = self.package.get_newest_version()
            if self.branch is None:
                self.problems.append("no versions in package")
        else:
            for version in self.package.get_versions():
                if version.is_version(self.version_name):
                    self.branch = self.package.get_version(version)
                    break
            if self.branch is None:
                self.problems.append(
                    "could not find version '" + self.version_name +
                    "' in package; available versions are '" +
                    "', '".join([
                        str(ver) for ver in self.package.get_versions()]) +
                    "'"
                )

        if self.branch is not None:
            self.problems.extend(
                [str(branch) for branch in self.branch.schema_version.problems])

    def set_output(self, output_dir: str, directories: bool, force: bool):
        if directories:
            output_dir = os.path.join(output_dir, self.package_name)

        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            self.problems.append("output directory '" + output_dir +
                                 "' exists but is not a directory")
        elif os.path.isdir(output_dir) and not force:
            self.problems.append("output directory '" + output_dir +
                                 "' exists but force flag not set; will not " +
                                 "overwrite")
        else:
            self.out_dir = output_dir


if __name__ == '__main__':

    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument('--version', action='version', version=VERSION)

    parser.add_argument("-v", "--verbose",
                        help="increase output verbosity",
                        action="store_true")
    parser.add_argument("-f", "--force",
                        help="overwrite any existing data",
                        action="store_true")
    parser.add_argument("-o", "--output",
                        help="directory to store the generated files",
                        action="store",
                        required=True)
    parser.add_argument("-d", "--directories",
                        help="""put each source directory into its own named
                        sub-directory under the output directory""",
                        action="store_true")
    parser.add_argument("-p", "--platform",
                        help="SQL platform to generate for",
                        action="store",
                        required=True)

    parser.add_argument('sources', metavar='source', nargs='+',
                        help="""source directory to use an input.  By default,
                        this will pull in the highest version number to
                        generate.  To generate one specific version, use the
                        format 'source/dir/name@1.2.3' to generate version 1.2.3
                        from the source directory source/dir/name.""")

    arg_values = parser.parse_args()

    gens = presquel.get_generator(arg_values.platform)
    if len(gens) <= 0:
        print("No generator found for " + arg_values.platform)
        sys.exit(1)
    gen = gens[0]

    sources = []
    problems = False
    for source in arg_values.sources:
        setup = SourceSetup(source)
        setup.load()
        setup.set_output(arg_values.output, arg_values.directories,
                         arg_values.force)
        if len(setup.problems) > 0:
            problems = True
            print("Problems discovered for " + source + ":")
            for problem in setup.problems:
                print("[" + source + "] " + str(problem))
        else:
            sources.append(setup)

    if problems:
        sys.exit(1)

    for setup in sources:
        assert isinstance(setup, SourceSetup)
        os.makedirs(setup.out_dir)
        branch_version = setup.branch.schema_version
        order_length = find_max_order_len(-1, branch_version.schema)
        name_format = ('{0:0' + str(order_length) + 'd}_{1}.sql')
        for schema in branch_version.schema:
            filename = os.path.join(
                setup.out_dir, name_format.format(
                    schema.order.items()[0], schema.name))
            print("Generating " + filename)
            with open(filename, 'w') as f:
                for script in gen.generate_base(schema):
                    f.write(script)
