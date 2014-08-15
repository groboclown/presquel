"""
Looks at a base directory to be the source of all the versions.  Each root
directory name is considered the version number, if it matches one of these
forms ('X' represents one or more decimal characters, 0-9):

    X
    vX
    vX_sometext
    X_sometext

Within those directories, all files (recursively) that end with a recognized
extension (.json, .xml, .yaml) are read as a schema file.
"""

from . import PARSERS_BY_EXTENSION
from ..model import (SchemaVersion, SchemaObject, Change)
import os.path


def find_files_for_version(version_dir_name):
    """
    An iterable discovery of the files within a version.

    :param version_dir_name:
    :return: iteration of the full file names within the directory
    """

    for root, dirs, files in os.walk(version_dir_name):
        for f in files:
            yield os.path.join(root, f)


def find_version_dirs(root_dir):
    """
    Finds all the version directories in the given root directory.  Returns
    these as a list of tuples (version_number, version_dir)

    :param root_dir:
    :return tuple: list of (dir index, full directory name)
    """

    print("DEBUG: find_version_dirs("+repr(root_dir)+")")
    for name in os.listdir(root_dir):
        print("DEBUG: --"+repr(name))
        full_name = os.path.join(root_dir, name)
        if os.path.isdir(full_name):
            if name.count("_") > 0:
                name = name[0: name.find("_")]
            if name.startswith("v"):
                name = name[1:]
            if name.isdigit():
                yield (int(name), full_name)


def parse_versions(root_dir):
    """
    Finds and parses all the schema versions in the given directory.  The
    returned list of schemas will be sorted, with the most recent version
    at the front of the list.

    :param root_dir:
    :return:
    """

    ret = []
    for (version_number, version_dir) in find_version_dirs(root_dir):
        changes = []
        schemas = []
        for file_name in find_files_for_version(version_dir):
            (root, ext) = os.path.splitext(file_name)
            if ext and len(ext) > 0:
                ext = ext.lower()
                if ext in PARSERS_BY_EXTENSION:
                    print("DEBUG: " + file_name)
                    with open(file_name, 'r') as f:
                        _split_changes_schemas(
                            PARSERS_BY_EXTENSION[ext].parse(file_name, f),
                            changes,
                            schemas)
        ret.append(SchemaVersion(version_number, changes, schemas))
    ret = sorted(ret)
    ret.reverse()
    return ret


def _split_changes_schemas(values, changes, schemas):
    for v in values:
        if isinstance(v, Change):
            changes.append(v)
        elif isinstance(v, SchemaObject):
            schemas.append(v)
        else:
            raise Exception("internal error: unexpected type " + str(type(v)) +
                            ": " + str(v))
