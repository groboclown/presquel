
"""
Helper utility for the generation of SQL from the analysis.
"""

from .analysis import (ProcessedForeignKeyConstraint, ColumnAnalysis,
                       ColumnSetAnalysis, AbstractProcessedConstraint)
from ..model.schema import (SqlConstraint, Table, View, Column,
                     LanguageConstraint)
from ..model.base import (SqlSet, SqlArgument, LanguageSet, LanguageArgument,
                          SqlString)


class ReadQueryData(object):
    def __init__(self, analysis_obj, platforms, language):
        assert isinstance(analysis_obj, ColumnSetAnalysis)

        # FIXME use the "language" for code parts if specified.  This
        # will be used when the language and sql parts of the constraint
        # are unified.

        join_clause = ''
        # include the foreign key here, for reference
        col_names = []
        col_query = []
        arguments = []
        where_ands = []

        for column in analysis_obj.columns_for_read:
            assert isinstance(column, ColumnAnalysis)

            handled = False
            if column.read_value is not None:
                constraint = column.read_value.constraint
                assert isinstance(constraint, SqlConstraint)
                sql_set = constraint.sql
                assert isinstance(sql_set, SqlSet)
                value = sql_set.get_for_platform(platforms).sql

                if value is not None:
                    handled = True
                    col_names.append(column.sql_name)
                    for arg in sql_set.arguments:
                        # FIXME this is mysql specific syntax.
                        # FIXME this should instead use the SqlConstraint
                        # method to get the replaced string.
                        value = value.replace('{' + arg + '}', ':' + arg)
                    # FIXME is this the correct thing to do?
                    col_query.append(value + ' AS ' + column.sql_name)
                    arguments.extend(sql_set.arguments)

            if not handled:
                col_query.append(analysis_obj.sql_name + '.' + column.sql_name +
                                 ' AS ' + column.sql_name)
                col_names.append(column.sql_name)

            # These shouldn't exist, and instead the user should use views,
            # but that's a personal thing.  If they really want it, here it is.
            for qr in column.query_restrictions:
                assert isinstance(qr, AbstractProcessedConstraint)
                constraint = qr.constraint
                assert isinstance(constraint, SqlConstraint)
                sql_set = constraint.sql
                assert isinstance(sql_set, SqlSet)
                value = sql_set.get_for_platform(platforms)
                if value is not None:
                    for arg in constraint.arguments:
                        value = value.replace('{' + arg + '}', ':' + arg)
                        arguments.append(arg)
                    where_ands.append(value)

        fki = 0
        for fkey in analysis_obj.foreign_keys_analysis:
            assert isinstance(fkey, ProcessedForeignKeyConstraint)
            # Even if the foreign key is an "owner" for this table, we can pull
            # it in if the declaration says so.
            if fkey.join:
                # Explicit desire to always join on this foreign table.
                fki += 1
                fk_name = 'k' + str(fki)

                column_analysis = analysis_obj.get_column_analysis(fkey.column)
                assert isinstance(column_analysis, ColumnAnalysis)
                if column_analysis.is_nullable:
                    join_clause += ' LEFT OUTER JOIN '
                else:
                    join_clause += ' INNER JOIN '
                join_clause += (fkey.fk_table_name + ' ' + fk_name + ' ON ' +
                                fk_name + '.' + fkey.fk_column_name + ' = ' +
                                analysis_obj.sql_name + '.' + fkey.column_name)
                if fkey.remote_table is not None:
                    rtab = fkey.remote_table
                    assert (isinstance(rtab, Table) or
                            isinstance(rtab, View))
                    for fcol in rtab.columns:
                        assert isinstance(fcol, Column)
                        query_name = fkey.fk_table_name + '__' + fcol.name
                        col_names.append(query_name)
                        col_query.append(fkey.fk_table_name + '.' + fcol.name +
                                         ' AS ' + query_name)

        from_clause = ' FROM ' + analysis_obj.sql_name + join_clause
        where_clause = ''
        if len(where_ands) > 0:
            where_clause = ' WHERE ' + (' AND '.join(where_ands))
        select_columns_clause = ','.join(col_query)
        sql = 'SELECT ' + select_columns_clause + from_clause + where_clause

        self.column_names = col_names
        self.column_queries = col_query
        self.analysis_obj = analysis_obj
        self.arguments = arguments
        self.select_columns_clause = select_columns_clause
        self.from_clause = from_clause
        self.join_clause = join_clause
        self.where_clause = where_clause
        self.sql = sql

        # FIXME these could be full-on objects
        self.where_clauses = where_ands

        self.has_join = len(join_clause) > 0
        self.has_where_clauses = len(where_ands) > 0


class InputValue(object):
    """
    Defines how the code should generate SQL that may require the language
    to dynamically construct the SQL, an/or SQL that has parameterized
    arguments.

    This is used by the converter.PrepSqlConverter to generate code.
    """

    @staticmethod
    def create_direct_value(column, is_required, is_where_clause):
        sql_str = "{" + column.sql_name + "}"
        if is_where_clause:
            sql_str = column.sql_name + " = " + sql_str
        sstr = SqlString(sql_str, "universal", [ "any" ])
        sql = SqlSet([ sstr ], [ column.name_as_sql_argument ])
        return InputValue(column, is_required, is_where_clause,
            None, None, sql, None)

    @staticmethod
    def create_specified(column, is_required, is_where_clause, code, sql):
        return InputValue(column, is_required, is_where_clause, code, None,
            sql, None)

    @staticmethod
    def create_default(column, is_required, is_where_clause, code, sql):
        return InputValue(column, is_required, is_where_clause, None, code,
            None, sql)

    @staticmethod
    def create_specified_constraint(column, is_required, is_where_clause,
            constraint):
        # FIXME in the future, this will need to use the unified type
        if isinstance(constraint, SqlConstraint):
            return InputValue.create_specified(
                column, is_required, is_where_clause, None, constraint.sql)
        elif isinstance(constraint, LanguageConstraint):
            return InputValue.create_specified(
                column, is_required, is_where_clause, constraint.code, None)
        else:
            raise Exception("Unknown kind of value constraint")

    @staticmethod
    def create_default_constraint(column, is_required, is_where_clause,
            constraint):
        # FIXME in the future, this will need to use the unified type
        if isinstance(constraint, SqlConstraint):
            return InputValue.create_default(
                column, is_required, is_where_clause, None, constraint.sql)
        elif isinstance(constraint, LanguageConstraint):
            return InputValue.create_default(
                column, is_required, is_where_clause, constraint.code, None)
        else:
            raise Exception("Unknown kind of value constraint")

    def __init__(self, column, is_required, is_where_clause,
            specified_code, default_code,
            specified_sql_set, default_sql_set):
        object.__init__(self)
        assert isinstance(column, ColumnAnalysis)
        assert (specified_code is None or
                isinstance(specified_code, LanguageSet))
        assert (specified_sql_set is None or
                isinstance(specified_sql_set, SqlSet))
        assert (default_code is None or
                isinstance(default_code, LanguageSet))
        assert (default_sql_set is None or
                isinstance(default_sql_set, SqlSet))

        self.column_name = column.sql_name
        self.column = column
        self.is_where_clause = is_where_clause

        self.__is_required = is_required
        self.__specified_code = specified_code
        self.__default_code = default_code
        self.__specified_sql_set = specified_sql_set
        self.__default_sql_set = default_sql_set

        # Validation: the default arguments must be, at most, within the
        # list of specified arguments.  This means that we don't allow for
        # default values to require arguments that aren't required by the
        # specified values (makes sense).  The SQL arguments *can* also be the
        # inputs given to the code, though.
        # FIXME validation of above.

    def get_code(self, is_specified):
        """

        :return: the LanguageSet.  The code, if given, will generate as output
            the sql into an output variable.
        """
        if is_specified:
            return self.__specified_code
        else:
            return self.__default_code

    def get_sql(self, is_specified):
        """

        :return: the SqlSet.
        """
        if is_specified:
            return self.__specified_sql_set
        else:
            return self.__default_sql_set

    @property
    def is_required(self):
        """
        Do the constraints require a value to always be specified?
        """
        return self.__is_required


class UpdateCreateQuery(object):
    """
    A parent class for specifying data to be input into a table.
    """
    def __init__(self, analysis_obj):
        """
        :param analyis_obj ColumnSetAnalysis:
        """
        assert isinstance(analysis_obj, ColumnSetAnalysis)

        # Columns that are updated by the query
        self.__columns = self._get_columns_for(analysis_obj)

        # list of all the (code) input arguments required.  Order is important.
        # list of strings
        self.__required_input_arguments = []

        # list of all the (code) optional input arguments.  Order is important.
        # list of strings
        self.__optional_input_arguments = []

        # List of all the required columns as InputValue instances.
        # list of InputValue
        self.__required_input_values = []

        # List of all the optional columns as InputValue instances.
        # list of InputValue
        self.__optional_input_values = []

        # Mapping of each InputValue to all the input arguments required.
        # Thus, the code can check if each of the arguments was given, then
        # that optional value can be used.  If they aren't all given, then
        # the default value should be used on the input.
        # Map{InputValue => argument list(list of str)}
        self.__value_arguments = {}

        # List of all where values
        self.__where_values = []

        # Column mapping to the inputs (list of InputValue)
        self.__column_to_values = {}

        # Note: don't use sets.  Order is very important for the arguments.

        required = []
        optional = []

        for col in self.columns:
            assert isinstance(col, ColumnAnalysis)

            value_set = list(self._create_values(col, False))
            assert len(value_set) == 1
            value_set.extend(self._create_values(col, True))
            self.__column_to_values[col] = value_set
            is_required = False
            for val in value_set:
                assert isinstance(val, InputValue)
                is_required = is_required or val.is_required

            for value in value_set:
                assert isinstance(value, InputValue)
                out_list = required
                arg_list_list = [ value.get_code(True), value.get_sql(True) ]
                if is_required:
                    self.__required_input_values.append(value)
                else:
                    self.__optional_input_values.append(value)
                    out_list = optional
                    arg_list_list.extend([ value.get_code(False),
                                          value.get_sql(False) ])
                for arg_list in arg_list_list:
                    if arg_list is not None:
                        for arg in arg_list.arguments:
                            out_list.append(arg.name)

        for name in required:
            if name not in self.__required_input_arguments:
                self.__required_input_arguments.append(name)
        for name in optional:
            if (name not in self.__required_input_arguments and
                    name not in self.__optional_input_arguments):
                self.__optional_input_arguments.append(name)


        for value_list in [ self.__required_input_values,
                            self.__optional_input_values ]:
            for value in value_list:
                if value.is_where_clause:
                    self.__where_values.append(value)
                args = []
                code = value.get_code(True)
                if code is not None:
                    for arg in code.arguments:
                        assert isinstance(arg, LanguageArgument)
                        args.append(arg)
                sql = value.get_sql(True)
                if sql is not None:
                    for arg in sql.arguments:
                        assert isinstance(arg, SqlArgument)
                        args.append(arg)
                self.__value_arguments[value] = tuple(args)

    @property
    def columns(self):
        """
        All the columns that the user specifies to perform this action.
        """
        return self.__columns

    @property
    def required_input_arguments(self):
        """
        :return list(str): the string names of the arguments required by
            the generated source code.
        """
        return self.__required_input_arguments

    @property
    def optional_input_arguments(self):
        """
        :return list(str): the string names of the arguments optionally used by
            the generated source code.
        """
        return self.__optional_input_arguments

    @property
    def required_input_values(self):
        """
        :return list(InputValue):
        """
        return self.__required_input_values

    @property
    def optional_input_values(self):
        """
        :return list(InputValue):
        """
        return self.__optional_input_values

    @property
    def value_arguments(self):
        """
        :return map(InputValue -> LanguageArgument | SqlArgument): All the
                arguments for a given value.
        """
        return self.__value_arguments

    @property
    def where_values(self):
        """
        All the InputValue instances used in where clauses (list)
        :return list(InputValue):
        """
        return self.__where_values

    @property
    def column_to_values(self):
        """
        :return dict(ColumnAnalysis, list(InputValue)): column mapping to the
            inputs
        """
        return self.__column_to_values

    def _get_columns_for(self, analysis_obj):
        """
        :return list(ColumnAnalysis):
        """
        raise NotImplementedError()

    def _create_values(self, column, is_where_clause):
        """
        :return list(InputValue):
        """
        raise NotImplementedError()


class UpdateQuery(UpdateCreateQuery):
    """
    Handles the creation of the parts of the update query.

    The update query has 3 sections: the required parameters (must be supplied
    by the user), the optional parameters (may be provided, but doesn't have to,
    and can have a value (code or sql) if the user didn't give it),
    and the constraints.

    The update also defines the primary key columns, which are not added to the
    list of optional or required values, because these cannot be updated in
    the table.  Instead, these are used as part of the where clause.
    """
    def __init__(self, analysis_obj):
        UpdateCreateQuery.__init__(self, analysis_obj)
        self.__primary_key_columns = []
        self.__primary_key_values = []
        for col in analysis_obj.columns_analysis:
            assert isinstance(col, ColumnAnalysis)
            if col.is_primary_key:
                self.__primary_key_columns.append(col)
                if col in self.column_to_values:
                    self.where_values.extend(self.column_to_values[col])
                    self.__primary_key_values.extend(self.column_to_values[col])
                else:
                    val = InputValue.create_direct_value(col, True, True)
                    self.__primary_key_values.append(val)
                    self.where_values.append(val)

        # TODO If there is just one optional input value, it should be requried

    @property
    def primary_key_columns(self):
        """
        :return list(ColumnAnalysis): primary key columns
        """
        return self.__primary_key_columns

    @property
    def primary_key_values(self):
        """
        :return list(InputValue):
        """
        return self.__primary_key_values

    def _get_columns_for(self, analysis_obj):
        assert isinstance(analysis_obj, ColumnSetAnalysis)
        ret = []
        for col in analysis_obj.columns_for_update:
            assert isinstance(col, ColumnAnalysis)
            if not col.is_primary_key:
                ret.append(col)
        return ret

    def _create_values(self, column, is_where_clause):
        assert isinstance(column, ColumnAnalysis)
        is_required = column.update_required or column.is_primary_key

        if is_where_clause:
            values = column.update_restrictions
        else:
            # Can be None
            values = [ column.update_value ]
            if (values[0] is not None and (values[0].arguments is None or
                    len(values[0].arguments) <= 0)):
                is_required = True

        ret = []
        for val in values:
            if val is None:
                # Add the value directly
                ret.append(InputValue.create_direct_value(column, is_required,
                           is_where_clause))
            else:
                assert isinstance(val, AbstractProcessedConstraint)
                ret.append(InputValue.create_specified_constraint(
                    column, is_required, is_where_clause, val.constraint))
        return ret


class CreateQuery(UpdateCreateQuery):
    """
    Handles the creation of the parts of the insert query.

    The update query has 3 sections: the required parameters (must be supplied
    by the user), the optional parameters (may be provided, but doesn't have to,
    and can have a value (code or sql) if the user didn't give it),
    and the constraints.
    """
    def __init__(self, analysis_obj):
        UpdateCreateQuery.__init__(self, analysis_obj)
        assert isinstance(analysis_obj, ColumnSetAnalysis)

        # names of columns that the database creates.
        # There can be only one of these.
        self.generated_column_name = None

        for col in analysis_obj.columns_analysis:
            assert isinstance(col, ColumnAnalysis)
            if col.auto_gen:
                if self.generated_column_name is not None:
                    raise Exception("multiple auto-generated column values")
                self.generated_column_name = col.sql_name

    def _get_columns_for(self, analysis_obj):
        assert isinstance(analysis_obj, ColumnSetAnalysis)
        return analysis_obj.columns_for_create

    def _create_values(self, column, is_where_clause):
        assert isinstance(column, ColumnAnalysis)
        is_required = True

        if is_where_clause:
            values = column.create_restrictions
        else:
            # Can be None
            values = [column.create_value]
            # Default values are value types, which are specified in the dbs.
            if column.default_value is not None:
                is_required = False
            # If there are no arguments to the value, then the value is still
            # required, but does not have any user arguments.

        ret = []
        for val in values:
            if val is None:
                # Add the value directly
                ret.append(InputValue.create_direct_value(column, is_required,
                           is_where_clause))
            else:
                assert isinstance(val, AbstractProcessedConstraint)

                ret.append(InputValue.create_specified_constraint(
                    column, is_required, is_where_clause, val.constraint))
        return ret
