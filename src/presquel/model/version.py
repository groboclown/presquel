"""
Manages the different versions of the schema.
"""

from .schema import (SchemaObject)


class SchemaVersion(object):
    """
    Represents a single version of the schema, along with the changes to
    get here from the previous version.

    The "version" must be an integer or a list.
    """
    def __init__(self, version, top_changes, schema):
        object.__init__(self)

        if isinstance(version, int):
            version = [ version ]
        if not (isinstance(version, list) or isinstance(version, tuple)):
            raise Exception('"version" must be a list or int, found ' + repr(version))
        for vpt in version:
            assert isinstance(vpt, int)

        assert isinstance(schema, list) or isinstance(schema, tuple)
        self.__version = tuple(version)
        self.__top_changes = sorted(top_changes)
        self.__schema = sorted(schema)

    @property
    def version(self):
        return self.__version

    @property
    def top_changes(self):
        return self.__top_changes

    @property
    def schema(self):
        for s in self.__schema:
            assert isinstance(s, SchemaObject)
        return self.__schema

    def __sub__(self, other):
        """Compare version numbers in an abstract way.  Returns negative if this
        is < that, positive if this is > that, or 0 if they are equal."""
        assert isinstance(other, SchemaVersion)
        for idx in range(0, len(self.version)):
            if idx >= len(other.version):
                # The passed-in version has more numbers than this one,
                # so it is a later version
                return -1
            diff = self.version[idx] - other.version[idx]
            if diff != 0:
                return diff
                # The numbers are equal, so keep going down

        # At this point, the versions are either the same, or this version has
        # more numbers after itself than the passed-in version.
        # If this version has more numbers, then it comes after (> 0).
        return len(self.version) - len(other.version)

    def __lt__(self, version):
        return self - version < 0

    def __le__(self, version):
        return self - version <= 0

    def __gt__(self, version):
        return self - version > 0

    def __ge__(self, version):
        return self - version >= 0


class SchemaBranch(object):
    """
    Models how the SchemaVersion instances relate to each other.  This is a
    level of meta-data outside the
    """
