"""
Manages the different versions of the schema.
"""

from .base import (BaseObject, SchemaObjectType, Order)
from .schema import (SchemaObject)
from .change import (Change)


FATAL_TYPE = SchemaObjectType('fatal')
ERROR_TYPE = SchemaObjectType('error')
WARNING_TYPE = SchemaObjectType('warning')
NOTE_TYPE = SchemaObjectType('note')


class ErrorObject(BaseObject):
    """
    Defines a parse error or definition error associated with a schema
    version.
    """
    def __init__(self, source: BaseObject or None, comment: str,
                 source_name: str, source_pos: str or None=None,
                 source_line: int or None=None, source_col: int or None=None,
                 level: SchemaObjectType=ERROR_TYPE):
        order = Order([0, 0, 0])
        if source is not None:
            order = source.order
        BaseObject.__init__(self, order, comment, level)

        assert isinstance(source, BaseObject) or source is None
        assert isinstance(source_name, str)
        if source_pos is not None and len(source_pos) > 0:
            assert isinstance(source_pos, str)
            assert source_line is None
            assert source_col is None
        elif source_line is not None:
            source_pos = "line " + str(source_line)
            if source_col is not None:
                source_pos += ", column " + str(source_col)
        else:
            source_pos = None

        self.__source = source
        self.__source_name = source_name
        self.__source_pos = source_pos

    @property
    def source_name(self) -> str:
        """File name source of the problem."""
        return self.__source_name

    @property
    def source_pos(self) -> str or None:
        """Position in the file that contains the problem.  Can be None if
        the location is not known"""
        return self.__source_pos

    @property
    def source_location(self) -> str:
        """
        File name and position in the file where the problem occurred.
        """
        ret = self.source_name
        if self.source_pos is not None:
            ret += " @ " + self.source_pos
        return ret

    @property
    def source(self) -> BaseObject or None:
        return self.__source

    def set_source(self, source: BaseObject):
        assert self.__source is None
        assert isinstance(source, BaseObject)
        self.__source = source

    def __str__(self):
        return "Error: {} ; {}".format(self.comment, self.source_location)


class SchemaVersionNumber(object):
    """
    Represents a version number for a schema, which is a dewey decimal series
    of integers.

    :type versions: tuple[int] or list[int]
    """
    def __init__(self, versions: tuple or list):
        object.__init__(self)
        for vsn in versions:
            assert isinstance(vsn, int)

        self.__versions = tuple(versions)

    @property
    def decimals(self) -> tuple:
        """
        :rtype: tuple[int]
        """
        return self.__versions

    @property
    def depth(self) -> int:
        return len(self.__versions)

    def is_version(self, version_str: str) -> bool:
        return str(self) == version_str

    def is_parent_decimal_of(self, other) -> bool:
        """
        Returns ``True`` if self has the same decimal numbers up to
        a higher depth of the other, but has no other numbers below that.

        :type other: SchemaVersionNumber
        """
        assert isinstance(other, SchemaVersionNumber)
        if other.depth <= self.depth:
            return False

        for idx in range(self.depth):
            if other[idx] != self[idx]:
                return False

        # Other has the name numbers as self, plus some more.  So it's a
        # child
        return True

    def is_sibling_decimal_of(self, other) -> bool:
        """
        Returns ``True`` if self and other have the same depth, and same numbers
        up to the penultimate number.

        :type other: SchemaVersionNumber
        """
        assert isinstance(other, SchemaVersionNumber)
        if other.depth != self.depth:
            return False

        for idx in range(self.depth - 1):
            if other[idx] != self[idx]:
                return False

        # Both are at the same depth, and the parent numbers are the same.
        return True

    def __getitem__(self, item: int) -> int:
        assert isinstance(item, int)
        return self.__versions[item]

    def __contains__(self, item) -> bool:
        return item in self.__versions

    def __len__(self) -> int:
        return len(self.__versions)

    def __sub__(self, other) -> int:
        """Compare version numbers in an abstract way.  Returns negative if this
        is < that, positive if this is > that, or 0 if they are equal."""
        assert isinstance(other, SchemaVersionNumber)
        for idx in range(self.depth):
            if idx >= other.depth:
                # The passed-in version has more numbers than this one,
                # so it is a later version
                return -1
            diff = self[idx] - other[idx]
            if diff != 0:
                return diff
                # The numbers are equal, so keep going down

        # At this point, the versions are either the same, or this version has
        # more numbers after itself than the passed-in version.
        # If this version has more numbers, then it comes after (> 0).
        return self.depth - other.depth

    def __lt__(self, version) -> bool:
        return self - version < 0

    def __le__(self, version) -> bool:
        return self - version <= 0

    def __gt__(self, version) -> bool:
        return self - version > 0

    def __ge__(self, version) -> bool:
        return self - version >= 0

    def __eq__(self, other) -> bool:
        if not isinstance(other, SchemaVersionNumber):
            return False
        return self - other == 0

    def __hash__(self) -> int:
        return hash(self.decimals)

    def __str__(self) -> str:
        return ".".join([str(val) for val in self.decimals])

    def __repr__(self) -> str:
        return "SchemaVersionNumber({})".format(", ".join(
            [repr(dec) for dec in self.decimals]))


class SchemaVersion(object):
    """
    Represents a single version of the schema, along with the changes to
    get here from the previous version.

    The "version" must be an integer or a list of integers.

    :type top_changes: list[Change] or tuple[Change]
    :type schema: list[SchemaObject] or tuple[SchemaObject]
    :type errors: list[ErrorObject] or tuple[ErrorObject]
    """
    def __init__(self, package: str, version: SchemaVersionNumber,
                 top_changes: list or tuple,
                 schema: list or tuple,
                 errors: list or tuple):
        object.__init__(self)

        assert isinstance(package, str) and len(package) > 0
        self.__package = package

        assert isinstance(version, SchemaVersionNumber)
        self.__version = version

        assert isinstance(schema, list) or isinstance(schema, tuple)
        for sch in schema:
            assert isinstance(sch, SchemaObject)
        self.__schema = sorted(schema)

        for chg in top_changes:
            assert isinstance(chg, Change)
        self.__top_changes = sorted(top_changes)

        self.__problems = tuple(errors)

    @property
    def problems(self) -> tuple:
        """
        :rtype: tuple[ErrorObject]
        """
        return self.__problems

    @property
    def version(self) -> SchemaVersionNumber:
        return self.__version

    @property
    def package(self) -> str:
        return self.__package

    @property
    def top_changes(self):
        return self.__top_changes

    @property
    def schema(self) -> list:
        """
        :rtype: list[SchemaObject]
        """
        return self.__schema

    def all_changes(self) -> list:
        """
        list of both the top changes and the schema that were changed,
        correctly ordered.

        :rtype: list[SchemaObject or Change]
        """
        ret = [self.top_changes]
        for obj in self.schema:
            assert isinstance(obj, SchemaObject)
            if obj.has_any_changes():
                ret.append(obj)
        ret.sort()
        return ret

    # FIXME remove these once the corresponding checking code is removed
    def __lt__(self, version):
        raise Exception("compare version numbers instead")

    def __le__(self, version):
        raise Exception("compare version numbers instead")

    def __gt__(self, version):
        raise Exception("compare version numbers instead")

    def __ge__(self, version):
        raise Exception("compare version numbers instead")


class SchemaBranch(object):
    """
    Models how the SchemaVersion instances relate to each other.  This is a
    level of meta-data outside the schema definition.

    The SchemaVersion can be lazy-loaded.  This is done by passing a None
    value for ``branch``, and pass in a callable ``branch_loader`` that
    loads the ``SchemaBranch`` object; ``branch_loader`` is passed the
    corresponding ``SchemaVersionNumber`` as an argument, so that the same
    value can be reused.
    """
    def __init__(self, parent: object or None,
                 package: str,
                 branch: SchemaVersion or None=None,
                 branch_loader: callable or None=None,
                 version: SchemaVersionNumber or None=None):
        """
        :type parent: SchemaBranch or None
        """
        object.__init__(self)

        assert parent is None or isinstance(parent, SchemaBranch)
        assert isinstance(package, str)
        assert branch is None or isinstance(branch, SchemaVersion)
        assert branch_loader is None or callable(branch_loader)
        assert branch is None or branch_loader is None
        if branch_loader is not None:
            assert version is not None

        self.__parent = parent
        self.__package = package
        self.__branch = branch
        self.__branch_loader = branch_loader
        self.__version = version or branch.version

        # To allow building of the objects incrementally
        self._children = []

        if parent is not None:
            parent._children.append(self)

    @property
    def package(self) -> str:
        return self.__package

    @property
    def is_branch_loaded(self) -> bool:
        return self.__branch is not None

    @property
    def schema_version(self) -> SchemaVersion:
        if self.__branch is None:
            branch = self.__branch_loader(self.version)
            assert isinstance(branch, SchemaVersion)
            self.__branch = branch
        return self.__branch

    @property
    def version(self) -> SchemaVersionNumber:
        return self.__version

    @property
    def parent(self) -> None or object:
        """

        :rtype: SchemaBranch or None
        """
        return self.__parent

    @property
    def children(self) -> tuple:
        """
        :rtype: tuple[SchemaBranch]
        """
        return tuple(self._children)

    # def _is_ancestor(self, branch: SchemaBranch) -> bool:
    #    if branch == self.parent:
    #        return True
    #    if branch is not None:
    #        return self.parent._is_ancestor(branch)
    #    return False

    def __str__(self) -> str:
        return "Branch(" + self.package + " : " + str(self.version) + ")"


class SchemaPackage(object):
    """
    A collection of the branches.  It allows easy querying for specific
    version numbers, or the most recent branch.

    A package should only contain the versions for a single package, as their
    branching relationship should not go outside the package.
    """
    def __init__(self, package: str):
        assert isinstance(package, str)
        self.__package = package
        self.__version_map = {}

        # branches with no parents
        self.__first_branches = []

        # branches with unresolved parents
        self.__unresolved_parents_loaded = []
        self.__unresolved_parents_lazy = []

    @property
    def package(self) -> str:
        return self.__package

    @property
    def branches(self) -> tuple:
        """
        All resolved branches.

        :rtype: tuple[SchemaBranch]
        """
        return self.__version_map.values()

    @property
    def unresolved_branch_versions(self) -> list:
        """
        If a registered branch notes a particular version as its parent, but
        that parent is never registered, then the parent is marked as
        "unresolved", and is returned by this property.

        :rtype: list[SchemaVersionNumber]
        """
        ret = []
        for parent, branch in self.__unresolved_parents_loaded:
            assert isinstance(branch, SchemaVersion)
            ret.append(branch.version)

        for parent, branch_loader, version in self.__unresolved_parents_lazy:
            assert isinstance(version, SchemaVersionNumber)
            ret.append(version)

        return ret

    def get_versions(self) -> tuple:
        """
        :rtype: tuple[SchemaVersionNumber]
        """
        return self.__version_map.keys()

    def get_newest_version(self) -> SchemaBranch or None:
        if len(self.__version_map) <= 0:
            return None
        versions = list(self.get_versions())
        versions.sort(reverse=True)
        return self.__version_map[versions[0]]

    def get_version(self, version: SchemaVersionNumber) -> SchemaBranch or None:
        if version in self.__version_map:
            return self.__version_map[version]
        return None

    def add_branch_version(self, branch: SchemaVersion,
                           parent: SchemaBranch or SchemaVersionNumber or None):
        """
        Add an already-loaded schema version as a branch.
        """
        assert isinstance(branch, SchemaVersion)
        assert branch.package == self.package, (
            "tried to add " + str(branch) + " to a " + self.package + " group")
        assert branch.version not in self, "Already added branch " + str(branch)

        if parent is not None or parent not in self:
            assert isinstance(parent, SchemaVersionNumber), (
                "SchemaBranch objects should be created by the " +
                "SchemaPackage")

            # The parent hasn't been loaded yet.
            # See if it's in the pending list.
            self.__resolve_parents()

            if parent not in self:
                # the parent should be added later.
                self.__unresolved_parents_loaded.append([parent, branch])
                return

        if parent is not None:
            # get the real version
            parent = self[parent]
        sbr = SchemaBranch(parent, self.package, branch=branch)
        self.__version_map[branch.version] = sbr
        self.__resolve_parents()
        if parent is None:
            self.__first_branches.append(sbr)

    def add_branch_loader(self, branch_loader: callable,
                          version: SchemaVersionNumber,
                          parent: SchemaBranch or SchemaVersionNumber or None):
        """
        Add a lazy-loaded branch.
        """
        assert callable(branch_loader)
        assert isinstance(version, SchemaVersionNumber)
        assert version not in self, (
            "Already added branch " + self.package + " : " + str(version))

        if parent is not None and parent not in self:
            assert isinstance(parent, SchemaVersionNumber), (
                "SchemaBranch objects should be created by the " +
                "SchemaPackage")

            # The parent hasn't been loaded yet.
            # See if it's in the pending list.
            self.__resolve_parents()

            if parent not in self:
                # the parent should be added later.
                self.__unresolved_parents_lazy.append([
                    parent, branch_loader, version])
                return

        if parent is not None:
            # get the real version
            parent = self[parent]
        sbr = SchemaBranch(parent, self.package, branch_loader=branch_loader,
                           version=version)
        self.__version_map[version] = sbr
        self.__resolve_parents()
        if parent is None:
            self.__first_branches.append(sbr)

    def __resolve_parents(self):
        """
        Look through the list of unresolved branches, and check if their
        parent has been added yet.
        """

        search = True
        while search and (
                len(self.__unresolved_parents_loaded) +
                len(self.__unresolved_parents_lazy) > 0):
            search = False
            remove = []
            for item in self.__unresolved_parents_loaded:
                parent, branch = item
                assert isinstance(parent, SchemaVersionNumber)
                assert isinstance(branch, SchemaVersion)
                if parent in self:
                    self.add_branch_version(branch, parent)
                    remove.append(item)
                    search = True
            for item in remove:
                self.__unresolved_parents_loaded.remove(item)
            remove = []
            for item in self.__unresolved_parents_lazy:
                parent, branch_loader, version = item
                assert isinstance(parent, SchemaVersionNumber)
                assert callable(branch_loader)
                assert isinstance(version, SchemaVersionNumber)
                if parent in self:
                    self.add_branch_loader(branch_loader, version, parent)
                    remove.append(item)
                    search = True
            for item in remove:
                self.__unresolved_parents_lazy.remove(item)

    def __len__(self) -> int:
        return len(self.__version_map)

    def __getitem__(self, item) -> SchemaBranch:
        if isinstance(item, SchemaVersion):
            return self.__version_map[item.version]
        if isinstance(item, SchemaVersionNumber):
            return self.__version_map[item]
        if isinstance(item, SchemaBranch):
            return self.__version_map[item.version]
        raise Exception('invalid argument type ' + type(item))

    def __contains__(self, item) -> bool:
        if isinstance(item, SchemaVersion):
            return item.version in self.__version_map
        if isinstance(item, SchemaVersionNumber):
            return item in self.__version_map
        if isinstance(item, SchemaBranch):
            return item.version in self.__version_map
        return False
