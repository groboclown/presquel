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
from ..model.version import (
    SchemaVersion, SchemaPackage, SchemaVersionNumber, SchemaBranch, ErrorObject
)
from ..model.base import (BaseObject)
from ..model.change import (Change)
from ..model.schema import (SchemaObject)
import os
import re


def find_version_dirs(root_dir):
    """
    Finds all the version directories in the given root directory.  Returns
    these as a list of tuples (version_number, version_dir)

    :param root_dir:
    :return tuple: list of (dir index, full directory name)
    """
    # print("DEBUG: find_version_dirs("+repr(root_dir)+")")
    for name in os.listdir(root_dir):
        # print("DEBUG: --"+repr(name))
        full_name = os.path.join(root_dir, name)
        if os.path.isdir(full_name):
            if name.count("_") > 0:
                name = name[0: name.find("_")]
            if name.startswith("v"):
                name = name[1:]
            if name.isdigit():
                yield (int(name), full_name)


def parse_branches(root_dir) -> SchemaPackage:
    """
    Finds and parses all the schema versions in the given directory.  The
    returned list of schemas will be sorted, with the most recent version
    at the front of the list.

    :param root_dir:
    :return:
    """

    # FIXME


DEFAULT_VERSION_PATTERN_STR = "(?:v|\\.|_)(\\d+)"
DEFAULT_VERSION_PATTERN = re.compile(DEFAULT_VERSION_PATTERN_STR)
DEFAULT_NAME_PATTERN = re.compile("(" + DEFAULT_VERSION_PATTERN_STR + ")+")
MANIFEST_FILE_NAME = '_manifest.yaml'


class VersionMetadata(object):
    """
    Default metadata version.  Loads the branch, using the base directory name
    as the version number.
    """
    def __init__(self, base_dir: str, package: str,
                 version_numbers: tuple(int)):
        object.__init__(self)
        self.__basedir = base_dir
        self.__package = package

        self.__name = os.path.basename(base_dir)
        self.__version = SchemaVersionNumber(version_numbers)
        self.__has_known_parent_version = False
        self.__known_parent_version = None

    @staticmethod
    def matches(package: str, base_dir: str):
        name = os.path.basename(base_dir)
        if DEFAULT_NAME_PATTERN.fullmatch(name) is not None:
            # convert the list of version strings to integers
            version_strings = DEFAULT_VERSION_PATTERN.findall(name)
            numbers = []
            for ver in version_strings:
                numbers.append(int(ver))
            return VersionMetadata(base_dir, package, numbers)
        return None

    @property
    def version(self) -> SchemaVersionNumber:
        return self.__version

    @property
    def package(self) -> str:
        return self.__package

    @property
    def has_known_parent_version(self) -> bool:
        return self.__has_known_parent_version

    @property
    def known_parent_version(self) -> SchemaVersionNumber:
        return self.__known_parent_version

    def load_branch(self, parent_version: SchemaVersionNumber) -> SchemaBranch:
        """
        Relies upon the caller to properly construct the parent version, if this
        object doesn't directly declare it.
        """
        if (self.has_known_parent_version and
                parent_version != self.known_parent_version):
            raise Exception("version number mismatch")

        return SchemaBranch(
            parent_version, self.__package,
            branch_loader=self.load_version, version=self.version)

    def load_version(self) -> SchemaVersion:
        """
        Load the version data.
        """

        changes = []
        schema = []
        errors = []

        # Recurse in the directory
        for root, dirs, files in os.walk(self.__basedir):
            for file_name in files:
                if file_name.strip().lower() == MANIFEST_FILE_NAME:
                    continue
                name = os.path.join(root, file_name)
                with open(file_name, 'r', encoding='UTF-8') as stream:
                    values = VersionMetadata.load_file(name, stream)
                    for value in values:
                        if isinstance(value, Change):
                            changes.append(value)
                        elif isinstance(value, SchemaObject):
                            schema.append(value)
                        elif isinstance(value, ErrorObject):
                            errors.append(value)
                        else:
                            raise Exception(file_name + ": invalid return type")
        return SchemaVersion(
            self.package, self.version, changes, schema, errors)

    @staticmethod
    def load_file(source_name, stream) -> tuple(BaseObject):
        ext = os.path.splitext(source_name)[1]
        return PARSERS_BY_EXTENSION[ext].parse(source_name, stream)
