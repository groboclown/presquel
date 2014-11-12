"""
Classes that add an additional layer of analysis upon the schema model.
"""

from ..model.version import (SchemaVersion)
from ..model.base import (SqlArgument)
from ..model.schema import (SchemaObject, Column, Table, View, Constraint,
                            SqlConstraint)


class AnalysisModel(object):
    """
    Top-level schema analysis parser and container.

    All parsing is done in this class and its subclasses.
    """

    def __init__(self):
        object.__init__(self)
        self.__schemas = []
        self.__schema_by_name = {}
        self.__schema_packages = {}
        self.__schema_analysis = {}

    def add_version(self, package_name, schema_version):
        """
        Add a new schema version to this model.  This should not contain
        multiple versions of the same schema, but rather a single version of
        multiple schemas.

        :param package_name:
        :param schema_version: SchemaVersion
        :return:
        """
        assert isinstance(schema_version, SchemaVersion)
        for schema in schema_version.schema:
            assert isinstance(schema, SchemaObject)
            name = schema.full_name
            if name in self.__schema_by_name:
                raise Exception("already registered schema with name " +
                                name)
            self.__schema_by_name[name] = schema
            self.__schemas.append(schema)
            self.__schema_packages[schema] = package_name
            self.__schema_analysis[schema] = self._process_schema(schema)

    @property
    def schemas(self):
        return tuple(self.__schemas)

    def get_schema_named(self, name):
        if name not in self.__schema_by_name:
            return None
        return self.__schema_by_name[name]

    def get_schema_package(self, schema):
        return self.__schema_packages[schema]

    def get_analysis_for(self, schema):
        if isinstance(schema, str):
            schema = self.get_schema_named(schema)
        assert isinstance(schema, SchemaObject)
        return self.__schema_analysis[schema]

    def get_schemas_referencing(self, schema):
        """
        Find all the schemas that have a foreign key that references the given
        schema.

        :param schema:
        :return: list of (schema, ProcessedForeignKeyConstraint) pairs
        """
        if isinstance(schema, str):
            schema = self.get_schema_named(schema)
        assert isinstance(schema, SchemaObject)
        sa = self.get_analysis_for(schema)
        if sa is None:
            return []
        assert isinstance(sa, SchemaAnalysis)
        ret = []
        for a in self.__schema_analysis.values():
            if a != schema and isinstance(a, ColumnSetAnalysis):
                for fk in a.foreign_keys_analysis:
                    assert isinstance(fk, ProcessedForeignKeyConstraint)
                    if fk.fk_table_name == sa.sql_name:
                        ret.append((a.schema, fk))
                        break
        return ret

    def _process_schema(self, schema):
        assert isinstance(schema, SchemaObject)

        if isinstance(schema, Table):
            analysis = self._process_column_set(schema, False)
        elif isinstance(schema, View):
            analysis = self._process_column_set(schema, True)
        else:
            raise Exception("can't process " + repr(schema))
        analysis.update_references(self)
        return analysis

    def _process_column_set(self, schema, is_read_only):
        assert isinstance(schema, Table) or isinstance(schema, View)
        pkg = self.get_schema_package(schema)

        cols = []
        for column in schema.columns:
            cols.append(
                self._process_column(column, pkg, is_read_only))

        top_constraints = []
        for c in schema.constraints:
            top_constraints.append(
                self._process_constraint(schema, c, pkg, is_read_only))

        top_analysis = TopAnalysis(schema, pkg, top_constraints, is_read_only)

        return self._create_columnset_analysis(
            schema, self.__schema_packages[schema], cols, top_analysis,
            is_read_only)

    def _process_column(self, column, package, is_read_only):
        constraints_analysis = []
        for c in column.constraints:
            constraints_analysis.append(
                self._process_constraint(column, c, package, is_read_only))
        return self._create_column_analysis(
            column, package, constraints_analysis, is_read_only)

    def _process_constraint(self, column, constraint, package, is_read_only):
        assert isinstance(constraint, Constraint)

        if constraint.constraint_type in ['foreignkey',
                                          'falseforeignkey', 'fakeforeignkey']:
            return ProcessedForeignKeyConstraint(column, package, constraint)

        return AbstractProcessedConstraint(column, package, constraint)

    def _create_columnset_analysis(self, schema, package, column_analysis,
                                   top_analysis, is_read_only):
        return ColumnSetAnalysis(schema, package, tuple(column_analysis),
                                 top_analysis, is_read_only)

    def _create_column_analysis(self, column, package, constraints_analysis,
                                is_read_only):
        return ColumnAnalysis(column, package, constraints_analysis,
                              is_read_only)


class SchemaAnalysis(object):
    def __init__(self, schema_obj, package):
        object.__init__(self)
        assert isinstance(schema_obj, SchemaObject)
        assert hasattr(schema_obj, 'name')
        assert isinstance(package, str)
        self.__package = package
        self.__schema = schema_obj
        self.__sql_name = schema_obj.name

    @property
    def package(self):
        return self.__package

    @property
    def schema(self):
        return self.__schema

    @property
    def sql_name(self):
        return self.__sql_name

    def update_references(self, analysis_model):
        assert isinstance(analysis_model, AnalysisModel)
        # Nothing to do
        pass


class ColumnSetAnalysis(SchemaAnalysis):
    def __init__(self, schema_obj, package, columns_analysis, top_analysis,
                 is_read_only):
        SchemaAnalysis.__init__(self, schema_obj, package)
        assert isinstance(schema_obj, Table) or isinstance(schema_obj, View)
        assert isinstance(columns_analysis, tuple)
        assert isinstance(top_analysis, TopAnalysis)
        self.__columns_analysis = columns_analysis
        self.__top_analysis = top_analysis
        self.__is_read_only = is_read_only

    def update_references(self, analysis_model):
        assert isinstance(analysis_model, AnalysisModel)
        SchemaAnalysis.update_references(self, analysis_model)

        for c in self.__columns_analysis:
            c.update_references(analysis_model)
        self.__top_analysis.update_references(analysis_model)

    @property
    def is_read_only(self):
        return self.__is_read_only

    @property
    def columns_analysis(self):
        return self.__columns_analysis

    def get_column_analysis(self, column):
        """
        Find the column analysis for the given column

        :param column:
        :return:
        """
        if isinstance(column, str):
            for col in self.columns_analysis:
                if col.sql_name == column:
                    return col
            return None
        elif isinstance(column, Column):
            for col in self.columns_analysis:
                if col.schema == column:
                    return col
            return None
        else:
            raise Exception("column must be str or Column value")

    @property
    def top_analysis(self):
        return self.__top_analysis

    @property
    def foreign_keys_analysis(self):
        """

        :return: a list of ProcessedForeignKeyConstraint values for all
            foreign keys in this column set.
        """
        ret = []
        for cola in self.__columns_analysis:
            assert isinstance(cola, ColumnAnalysis)
            for ca in cola.constraints:
                if isinstance(ca, ProcessedForeignKeyConstraint):
                    ret.append(ca)
        return ret

    def get_selectable_column_lists(self):
        """

        :return: a list of list of __columns that can be used to query the
            schema.  The column information will be the Column schema object.
            These Column schema objects will only be from this table object,
            never from the joined tables.  That behavior must instead be done
            through a view.
        """
        ret = []
        for c in self.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.read_by:
                ret.append([c.schema])

        c = self.top_analysis
        assert isinstance(c, TopAnalysis)
        for col_set in c.column_index_sets:
            cis = []
            for col in col_set:
                assert isinstance(col, str)
                ca = self.get_column_analysis(col)
                if ca is None:
                    raise Exception("no schema for " + col + " in " + self.sql_name)
                cis.append(ca.schema)
            ret.append(cis)

        return ret

    def get_write_validations(self):
        """

        :return: list of pairs: (column, validation constraint).  If it
            comes from a top-level constraint, the column is None.
        """
        ret = []
        for v in self.top_write_validations:
            ret.append([None, v])
        for c in self.columns_analysis:
            for v in c.write_validations:
                ret.append([c.schema, v])
        return ret

    @property
    def top_write_validations(self):
        """

        :return: list of all top-level validations for read operations
        """
        ret = []
        c = self.top_analysis
        assert isinstance(c, TopAnalysis)
        ret.extend(c.write_validations)
        return ret

    @property
    def primary_key_columns(self):
        """
        Generally used for the delete creation.

        :return: the list of ColumnAnalysis which make up the primary key.
        """
        ret = None
        for c in self.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.is_primary_key:
                assert ret is None, "multiple primary keys"
                ret = [c]
        c = self.top_analysis
        assert isinstance(c, TopAnalysis)
        if c.primary_key_constraint is not None:
            assert ret is None, "multiple primary keys"
            con = c.primary_key_constraint
            assert isinstance(con, AbstractProcessedConstraint)
            ret = [self.get_column_analysis(cn)
                   for cn in con.constraint.column_names]
        if ret is None and len(c.unique_or_primary_sets) > 0:
            # Default to using the first unique index/key
            con = c.unique_or_primary_sets[0]
            assert isinstance(con, AbstractProcessedConstraint)
            ret = [self.get_column_analysis(cn)
                   for cn in con.constraint.column_names]
        return ret or []

    @property
    def columns_for_read(self):
        ret = []
        for c in self.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.is_read:
                ret.append(c)
        return ret

    @property
    def columns_for_create(self):
        """

        :return: the __columns which are involved in the creation of the rows.
            The objects are instances of ColumnAnalysis
        """
        if self.is_read_only:
            return []

        ret = []
        for c in self.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.allows_create:
                ret.append(c)
        return ret

    @property
    def columns_for_update(self):
        """

        :return: the __columns which are involved in updating rows
        """
        if self.is_read_only:
            return []

        ret = []
        for c in self.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.allows_update:
                ret.append(c)
        return ret


class ColumnAnalysis(SchemaAnalysis):
    def __init__(self, column, package, constraints_analysis, is_read_only):
        SchemaAnalysis.__init__(self, column, package)
        assert isinstance(column, Column)
        self.is_read_only = is_read_only

        self.is_primary_key = False
        self.is_read = True
        self.allows_create = not column.auto_increment
        self.allows_update = True
        self.default_value = column.default_value
        assert (self.default_value is None or
                isinstance(self.default_value, SqlConstraint))
        assert (self.default_value is None or
                len(self.default_value.arguments) <= 0)
        self.auto_gen = column.auto_increment
        self.update_value = None
        self.update_required = False
        self.create_value = None
        self.create_restrictions = []
        self.update_restrictions = []
        self.read_value = None
        self.constraints = []
        self.foreign_key = None
        self.read_by = False
        # By default, every column allows null unless you explicitly turn it off
        self.is_nullable = True
        self.query_restrictions = []
        self.write_validations = []
        self.__constraints_analysis = []

        for c in constraints_analysis:
            if c is None:
                continue
            assert isinstance(c, AbstractProcessedConstraint)
            self.__constraints_analysis.append(c)
            if isinstance(c, ProcessedForeignKeyConstraint):
                assert self.foreign_key is None
                self.foreign_key = c
                self.read_by = True
            elif (c.constraint.constraint_type.endswith('index') or
                    c.constraint.constraint_type.endswith('key')):
                self.read_by = True
                if c.constraint.constraint_type == 'primarykey':
                    self.is_primary_key = True
            elif c.constraint.constraint_type == 'initialvalue':
                con = c.constraint
                assert isinstance(con, SqlConstraint)
                self.create_value = c
                self.allows_create = True
            elif c.constraint.constraint_type == 'noupdate':
                self.allows_update = False
            elif c.constraint.constraint_type == 'notread':
                self.is_read = False
            elif c.constraint.constraint_type == 'constantquery':
                self.read_value = c
            elif c.constraint.constraint_type in [
                    'constantupdate', 'updatevalue']:
                self.update_value = c
            elif c.constraint.constraint_type == 'restrictquery':
                self.query_restrictions.append(c)
            elif c.constraint.constraint_type == 'notnull':
                self.is_nullable = False
            elif c.constraint.constraint_type in ['validatewrite', 'validate']:
                self.write_validations.append(c)
            elif c.constraint.constraint_type == 'valuerestriction':
                self.create_restrictions.append(c)
                self.update_restrictions.append(c)
            elif c.constraint.constraint_type == 'createrestriction':
                self.create_restrictions.append(c)
            elif c.constraint.constraint_type == 'updaterestriction':
                self.update_restrictions.append(c)
            elif c.constraint.constraint_type in [
                    'updaterequired', 'requiredupdate']:
                self.update_required = True

        self.read_by = self.read_by and self.is_read

    def update_references(self, analysis_model):
        assert isinstance(analysis_model, AnalysisModel)
        SchemaAnalysis.update_references(self, analysis_model)

        for c in self.__constraints_analysis:
            c.update_references(analysis_model)

    @property
    def name_as_sql_argument(self):
        return SqlArgument(self.sql_name, self.schema.value_type, False)

    @property
    def create_arguments(self):
        """
        Return all arguments used to create this column.  An empty list
        means that a default value will be used.  If the column is used
        as-is, then the column name is returned in the list.
        This will not return the values defined in the default argument list

        :return: list of strings
        """
        if self.auto_gen or self.is_read_only:
            return []
        elif self.create_value is not None:
            return getattr(self.create_value, 'arguments', [])
        else:
            return [self.name_as_sql_argument]

    @property
    def update_arguments(self):
        """

        :return: list of arguments
        """
        if self.is_read_only:
            return []
        elif self.update_value is not None:
            return self.create_value.arguments
        else:
            return [self.name_as_sql_argument]


class TopAnalysis(SchemaAnalysis):
    """
    An analysis of the constraints around a top-level object.

    @column_index_sets - a list of lists of column names (string).  Each
        entry in this list represents the __columns that can be selected
        together as a group.
    """

    def __init__(self, schema, package, constraints_analysis, is_read_only):
        SchemaAnalysis.__init__(self, schema, package)
        assert (isinstance(schema, Table) or isinstance(schema, View))

        self.is_read_only = is_read_only
        self.__constraints_analysis = []
        self.write_validations = []
        self.primary_key_constraint = None

        self.column_index_sets = []

        self.unique_or_primary_sets = []

        for c in constraints_analysis:
            if c is None:
                continue
            assert isinstance(c, AbstractProcessedConstraint)
            self.__constraints_analysis.append(c)

            if (c.constraint.constraint_type.endswith('index') or
                    c.constraint.constraint_type.endswith('key')):
                column_names = c.constraint.column_names
                if column_names is not None and len(column_names) > 0:
                    self.column_index_sets.append(column_names)
                    if c.constraint.constraint_type == 'primarykey':
                        assert self.primary_key_constraint is None
                        self.primary_key_constraint = c
                        self.unique_or_primary_sets.append(c)
                    elif c.constraint.constraint_type.count('unique') > 0:
                        self.unique_or_primary_sets.append(c)
            elif c.constraint.constraint_type in ['validatewrite', 'validate']:
                self.write_validations.append(c)


class AbstractProcessedConstraint(SchemaAnalysis):
    def __init__(self, column, package, constraint, name = None):
        SchemaAnalysis.__init__(self, constraint, package)

        self.column = column
        if column is not None and (isinstance(column, Table) or
                                   isinstance(column, View)):
            self.column = None

        assert self.column is None or isinstance(self.column, Column)
        assert isinstance(constraint, Constraint)

        self.constraint = constraint
        self.column_name = name or column.name

        self.arguments = getattr(constraint, 'arguments', [])


class ProcessedForeignKeyConstraint(AbstractProcessedConstraint):
    def __init__(self, column, package, constraint):
        AbstractProcessedConstraint.__init__(self, column, package, constraint)

        if '__columns' in constraint.details:
            raise Exception(column.name +
                            ": we do not handle multiple column foreign keys")
        self.is_owner = False
        if ('relationship' in constraint.details and
                constraint.details['relationship'].lower() == 'owner'):
            self.is_owner = True
        self.is_real_fk = constraint.constraint_type == 'foreignkey'
        self.fk_column_name = constraint.details['column']
        self.fk_table_name = constraint.details['table']
        self.remote_table = None
        self.join = False
        if ('pull' in constraint.details and
                constraint.details['pull'] == 'always'):
            self.join = True

    def update_references(self, analysis_model):
        assert isinstance(analysis_model, AnalysisModel)
        AbstractProcessedConstraint.update_references(self, analysis_model)

        schema = analysis_model.get_schema_named(self.fk_table_name)
        if schema is not None:
            self.remote_table = schema
