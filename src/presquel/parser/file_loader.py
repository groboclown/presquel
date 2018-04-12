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
    SchemaVersion, SchemaPackage, SchemaVersionNumber, ErrorObject
)
from ..model.change import (Change)
from ..model.schema import (SchemaObject)
import os
import re
import math
from yaml import load as load_yaml


def load_package(root_dir, package: str or None=None) -> SchemaPackage:
    """
    Finds and parses all the schema versions in the given directory.  The
    returned list of schemas will be sorted, with the most recent version
    at the front of the list.

    :param root_dir:
    :return:
    """

    if package is None:
        package = os.path.basename(root_dir)
        if len(package) <= 0:
            package = os.path.basename(os.path.dirname(root_dir))

    all_metadata = {}

    for name in os.listdir(root_dir):
        full_name = os.path.join(root_dir, name)
        if os.path.isdir(full_name):
            for matcher in VERSION_METADATA_FACTORIES:
                metadata_list = matcher(package, full_name)
                for metadata in metadata_list:
                    assert isinstance(metadata, VersionMetadata)
                    if metadata.version in all_metadata:
                        # FIXME make this just another error
                        raise Exception("multiple versions: " +
                                        str(metadata.version))
                    all_metadata[metadata.version] = metadata

    ret = SchemaPackage(package)

    # We now have all the versions.  The "natural" sort order of these will
    # create a structure where the implicit parent of a version follows the
    # sorting.
    versions = list(all_metadata.keys())
    versions.sort()
    for metadata in all_metadata.values():
        assert isinstance(metadata, VersionMetadata)
        parent = metadata.known_parent_version
        if not metadata.has_known_parent_version:
            idx = versions.index(metadata.version)
            if idx <= 0:
                # no parent: this is the highest known version
                parent = None
            else:
                parent = versions[idx - 1]
        metadata.add_to_package(ret, parent)

    return ret


DEFAULT_VERSION_PATTERN_STR = "(?:v|\\.|_)(\\d+)"
DEFAULT_VERSION_PATTERN = re.compile(DEFAULT_VERSION_PATTERN_STR)
DEFAULT_NAME_PATTERN = re.compile("(" + DEFAULT_VERSION_PATTERN_STR + ")+")
MANIFEST_FILE_NAME = '_manifest.yaml'
IGNORED_SCHEMA_FILES = (MANIFEST_FILE_NAME,)


class VersionMetadata(object):
    """
    Default metadata version.  Loads the branch, using the base directory name
    as the version number.
    """
    def __init__(self, base_dir: str, package: str,
                 version: SchemaVersionNumber,
                 parent_given: bool, parent_numbers: tuple or list or None,
                 problems: tuple or list):
        """
        :type parent_numbers: tuple[int] or list[int] or None
        :type problems: tuple[ErrorObject] or list[ErrorObject]
        """
        object.__init__(self)
        assert isinstance(base_dir, str) and len(base_dir) > 0
        self.__basedir = base_dir
        assert isinstance(package, str) and len(package) > 0
        self.__package = package

        assert isinstance(version, SchemaVersionNumber)
        self.__name = os.path.basename(base_dir)
        self.__version = version
        self.__has_known_parent_version = parent_given
        self.__known_parent_version = None
        if parent_given and parent_numbers is not None:
            self.__has_known_parent_version = SchemaVersionNumber(
                parent_numbers)
        self.__problems = problems

    @staticmethod
    def matches(package: str, base_dir: str) -> tuple:
        """
        Parse the directory, and extract all the VersionMetadata instances
        in this directory.

        This specific implementation returns only the one directory, if the
        name matches the dewey decimal system convention.

        :rtype: tuple[VersionMetadata]
        """
        assert isinstance(base_dir, str) and len(base_dir) > 0
        assert isinstance(package, str) and len(package) > 0
        name = os.path.basename(base_dir)
        manifest_file = os.path.join(MANIFEST_FILE_NAME)
        problems = []
        if os.path.isfile(manifest_file):

            with open(manifest_file, 'r', encoding='UTF-8') as stream:
                manifest = load_yaml(stream)
            parent_given = False
            parent_version = None
            version = None
            if 'parent' in manifest:
                val = manifest['parent']
                parent_given = True
                if isinstance(val, int):
                    parent_given = True
                    parent_version = SchemaVersionNumber([val])
                elif isinstance(val, float):
                    problems.append(ErrorObject(
                        None, 'parent version must be a string',
                        manifest_file))
                    parent_version = SchemaVersionNumber([math.floor(val)])
                elif isinstance(val, str):
                    parent_version = _to_version(val, DEFAULT_VERSION_PATTERN)
                    if parent_version is None:
                        problems.append(ErrorObject(
                            None, 'parent version does not match pattern',
                            manifest_file))
                elif val is not None:
                    problems.append(ErrorObject(
                        None, 'parent version cannot be parsed; found ' +
                        repr(val), manifest_file))
            if 'version' in manifest:
                val = manifest['version']
                if isinstance(val, int):
                    version = SchemaVersionNumber([val])
                elif isinstance(val, float):
                    problems.append(ErrorObject(
                        None, 'version must be a string', manifest_file))
                    version = SchemaVersionNumber([math.floor(val)])
                elif isinstance(val, str):
                    version = _to_version(val, DEFAULT_VERSION_PATTERN)
                    if version is None:
                        problems.append(ErrorObject(
                            None, 'version does not match pattern',
                            manifest_file))
                else:
                    problems.append(ErrorObject(
                        None, 'cannot understand version: ' + repr(val),
                        manifest_file))
            if 'package' in manifest:
                val = manifest['package']
                if isinstance(val, str) and len(val) > 0:
                    package = manifest['package']
                else:
                    problems.append(ErrorObject(
                        None, 'invalid package name', manifest_file))

            # try to match the directory name
            if version is None:
                val = _to_version(name, DEFAULT_VERSION_PATTERN)
                if val is None:
                    problems.append(ErrorObject(
                        None, 'no version number in manifest, and directory '
                        'name does not match pattern',
                        manifest_file))
                    return tuple()
            return tuple(VersionMetadata(
                base_dir, package, version, parent_given, parent_version,
                problems))

        version = _to_version(name, DEFAULT_VERSION_PATTERN)
        if version is not None:
            return tuple([VersionMetadata(
                base_dir, package, version, False, None, problems)])

        return tuple()

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

    @property
    def problems(self):
        return self.__problems

    def add_to_package(self, package: SchemaPackage,
                       parent_version: SchemaVersionNumber or None):
        """
        Add the branch this represents into the package.
        """
        assert (isinstance(parent_version, SchemaVersionNumber) or
                parent_version is None)
        if self.has_known_parent_version:
            assert self.known_parent_version == parent_version
        package.add_branch_loader(self.load_version, self.version,
                                  parent_version)

    def load_version(self, version) -> SchemaVersion:
        """
        Load the version data.
        """

        assert self.version == version

        changes = []
        schema = []
        errors = list(self.problems)

        # Recurse in the directory
        # TODO: if a child directory contains the manifest file, use it
        # instead of this current version metadata
        for root, dirs, files in os.walk(self.__basedir):
            for file_name in files:
                lower = file_name.strip().lower()
                if lower in IGNORED_SCHEMA_FILES:
                    continue
                ext = os.path.splitext(lower)[1]
                if ext not in PARSERS_BY_EXTENSION:
                    continue
                name = os.path.join(root, file_name)
                with open(name, 'r', encoding='UTF-8') as stream:
                    values = PARSERS_BY_EXTENSION[ext].parse(
                        name, stream)
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


VERSION_METADATA_FACTORIES = [VersionMetadata.matches, ]


def _to_version(text, matcher):
    if matcher.fullmatch(text):
        ret = []
        vst = matcher.findall(text)
        # print("DEBUG: matched [{}] as [{}]".format(text, vst))
        for val in vst:
            ret.append(int(val))
        return SchemaVersionNumber(ret)
    return None
