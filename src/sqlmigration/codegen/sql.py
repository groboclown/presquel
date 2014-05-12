
"""
Helper utility for the generation of SQL from the analysis.
"""

from .analysis import (ProcessedForeignKeyConstraint, ColumnAnalysis,
                       ColumnSetAnalysis, AbstractProcessedConstraint)
from ..model import (SqlConstraint, SqlSet, Table, View, Column,
                     LanguageConstraint)


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
                    for arg in constraint.arguments:
                        # FIXME this is mysql specific syntax.
                        # FIXME this should instead use the SqlConstraint
                        # method to get the replaced string.
                        value = value.replace('{' + arg + '}', ':' + arg)
                    # FIXME is this the correct thing to do?
                    col_query.append(value + ' AS ' + column.sql_name)
                    arguments.extend(constraint.arguments)

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

        # TODO add optional where clauses.  These will be in the top analysis

        fki = 0
        for fk in analysis_obj.foreign_keys_analysis:
            assert isinstance(fk, ProcessedForeignKeyConstraint)
            # Even if the foreign key is an "owner" for this table, we can pull
            # it in if the declaration says so.
            if fk.join:
                # Explicit desire to always join on this foreign table.
                fki += 1
                fk_name = 'k' + str(fki)

                column_analysis = analysis_obj.get_column_analysis(fk.column)
                assert isinstance(column_analysis, ColumnAnalysis)
                if column_analysis.is_nullable:
                    join_clause += ' LEFT OUTER JOIN '
                else:
                    join_clause += ' INNER JOIN '
                join_clause += (fk.fk_table_name + ' ' + fk_name + ' ON ' +
                                fk_name + '.' + fk.fk_column_name + ' = ' +
                                analysis_obj.sql_name + '.' + fk.column_name)
                if fk.remote_table is not None:
                    rt = fk.remote_table
                    assert (isinstance(rt, Table) or
                            isinstance(rt, View))
                    for fcol in rt.columns:
                        assert isinstance(fcol, Column)
                        query_name = fk.fk_table_name + '__' + fcol.name
                        col_names.append(query_name)
                        col_query.append(fk.fk_table_name + '.' + fcol.name +
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

    @staticmethod
    def create_specified(column, is_required, is_where_clause, code, code_args,
                         sql, sql_args):
        return InputValue(column, is_required, is_where_clause, code_args,
                          code, [], None, sql_args, sql, [], None)

    @staticmethod
    def create_default(column, is_required, is_where_clause, code, code_args,
                       sql, sql_args):
        return InputValue(column, is_required, is_where_clause, [], None,
                          code_args, code, [], None, sql_args, sql)

    @staticmethod
    def create_specified_constraint(column, is_required, is_where_clause,
                                    constraint, platforms, language):
        # FIXME in the future, this will need to use the unified type
        if isinstance(constraint, SqlConstraint):
            # FIXME use an arg converter that is specific to the
            # language.  This right now is PHP.
            sql = constraint.sql_args(platforms, lambda a: ':' + a)
            sql_args = constraint.arguments
            return InputValue.create_specified(
                column, is_required, is_where_clause, None, [], sql, sql_args)
        elif isinstance(constraint, LanguageConstraint):
            code = constraint.code_for_language(language)
            code_args = constraint.arguments
            return InputValue.create_specified(
                column, is_required, is_where_clause, code, code_args, None, [])
        else:
            raise Exception("Unknown kind of value constraint")

    @staticmethod
    def create_default_constraint(column, is_required, is_where_clause,
                                  constraint, platforms, language):
        # FIXME in the future, this will need to use the unified type
        if isinstance(constraint, SqlConstraint):
            # FIXME use an arg converter that is specific to the
            # language.  This right now is PHP.
            sql = constraint.sql_args(platforms, lambda a: ':' + a)
            sql_args = constraint.arguments
            return InputValue.create_default(
                column, is_required, is_where_clause, None, [], sql, sql_args)
        elif isinstance(constraint, LanguageConstraint):
            code = constraint.code_for_language(language)
            code_args = constraint.arguments
            return InputValue.create_default(
                column, is_required, is_where_clause, code, code_args, None, [])
        else:
            raise Exception("Unknown kind of value constraint")

    def __init__(self, column, is_required, is_where_clause,
                 specified_code_args, specified_code,
                 default_code_args, default_code,
                 specified_sql_args, specified_sql, default_sql_args,
                 default_sql):
        object.__init__(self)
        assert isinstance(column, ColumnAnalysis)
        assert (specified_code_args is None or
                isinstance(specified_code_args, list) or
                isinstance(specified_code_args, tuple))
        assert (specified_sql_args is None or
                isinstance(specified_sql_args, list) or
                isinstance(specified_sql_args, tuple))
        assert (default_code_args is None or
                isinstance(default_code_args, list) or
                isinstance(default_code_args, tuple))
        assert (default_sql_args is None or
                isinstance(default_sql_args, list) or
                isinstance(default_sql_args, tuple))

        self.column_name = column.sql_name
        self.is_where_clause = is_where_clause

        self.__is_required = is_required
        self.__specified_code_args = tuple(specified_code_args or [])
        self.__specified_code = specified_code
        self.__default_code_args = tuple(default_code_args or [])
        self.__default_code = default_code
        self.__specified_sql_args = tuple(specified_sql_args or [])
        self.__specified_sql = specified_sql
        self.__default_sql_args = tuple(default_sql_args or [])
        self.__default_sql = default_sql

        # Validation: the default arguments must be, at most, within the
        # list of specified arguments.  This means that we don't allow for
        # default values to require arguments that aren't required by the
        # specified values (makes sense).  The SQL arguments *can* also be the
        # inputs given to the code, though.
        # FIXME validation of above.

    def get_code_arguments(self, is_specified):
        """

        :return: the list of arguments that the program passes to the
            code_value text.  The code, if given, will generate as output
            the sql input arguments.
        """
        if is_specified:
            return self.__specified_code_args
        else:
            return self.__default_code_args

    def get_sql_arguments(self, is_specified):
        """

        :return: the list of arguments that the program passes into the
            prepared statement.
        """
        if is_specified:
            return self.__specified_sql_args
        else:
            return self.__default_sql_args

    def get_code_value(self, is_specified):
        """

        :param is_specified: True if the arguments for this input value are
            passed to the method, or False if a default value must be given.
        :return: the code that generates the sql value, or None if there is no
            code, meaning the arguments are added directly into the prepared
            statement.
        """
        if is_specified:
            return self.__specified_code
        else:
            return self.__default_code

    def get_sql_value(self, is_specified):
        """

        :param is_specified: True if the arguments for this input value are
            passed to the method, or False if a default value must be given.
        :return: the sql to use as the value, or None if there is no sql
            value, meaning that no value or column is added into the
            sql statement.
        """
        if is_specified:
            return self.__specified_sql
        else:
            return self.__default_sql

    @property
    def is_required(self):
        """
        Do the constraints require a value to always be specified?
        """
        return self.__is_required


class UpdateCreateQuery(object):
    def __init__(self, analysis_obj, platforms, language):
        columns = self._get_columns_for(analysis_obj)

        # list of all the (code) input arguments required
        # list of strings
        self.required_input_arguments = []

        # list of all the (code) optional input arguments
        # list of strings
        self.optional_input_arguments = []

        # List of all the required columns as InputValue instances
        # list of InputValue
        self.required_input_values = []

        # List of all the optional columns as InputValue instances
        # list of InputValue
        self.optional_input_values = []

        # Mapping of optional InputValue to all the input arguments required.
        # Thus, the code can check if each of the arguments was given, then
        # that optional value can be used.  If they aren't all given, then
        # the default value should be used on the input.
        # Map{InputValue => argument list(list of str)}
        self.value_arguments = {}

        # Mapping of all InputValue to their where clause InputValue (list)
        self.where_values = {}

        # Note: don't use sets.  Order is very important for the arguments.

        for c in columns:
            assert isinstance(c, ColumnAnalysis)
            value_set = list(self._create_values(c, platforms, language, False))
            assert len(value_set) == 1
            value_set.extend(self._create_values(c, platforms, language, True))
            optional_args = []
            required = False
            for v in value_set:
                assert isinstance(v, InputValue)
                required = required or v.is_required

            for value in value_set:
                assert isinstance(value, InputValue)
                if required:
                    for a in value.get_code_arguments(True):
                        if a not in self.required_input_arguments:
                            self.required_input_arguments.append(a)
                    for a in value.get_sql_arguments(True):
                        if a not in self.required_input_arguments:
                            self.required_input_arguments.append(a)
                else:
                    for a in value.get_code_arguments(True):
                        if a not in optional_args:
                            optional_args.append(a)
                        if a not in self.optional_input_arguments:
                            self.optional_input_arguments.append(a)
                    for a in value.get_sql_arguments(True):
                        if a not in optional_args:
                            optional_args.append(a)
                        if a not in self.optional_input_arguments:
                            self.optional_input_arguments.append(a)

                    for a in value.get_code_arguments(False):
                        if a not in self.optional_input_arguments:
                            self.optional_input_arguments.append(a)
                    for a in value.get_sql_arguments(False):
                        if a not in self.optional_input_arguments:
                            self.optional_input_arguments.append(a)

            self.value_arguments[value_set[0]] = optional_args
            self.where_values[value_set[0]] = value_set[1:]

            if required:
                self.required_input_values.append(value_set[0])
            else:
                self.optional_input_values.append(value_set[0])

    def _get_columns_for(self, analysis_obj):
        raise Exception("not implemented")

    def _create_values(self, column, platforms, language, is_where_clause):
        raise Exception("not implemented")


class UpdateQuery(UpdateCreateQuery):
    """
    Handles the creation of the parts of the update query.

    The update query has 3 sections: the required parameters (must be supplied
    by the user), the optional parameters (may be provided, but doesn't have to,
    and can have a value (code or sql) if the user didn't give it),
    and the constraints.
    """
    def __init__(self, analysis_obj, platforms, language):
        UpdateCreateQuery.__init__(self, analysis_obj, platforms, language)
        pass

    def _get_columns_for(self, analysis_obj):
        assert isinstance(analysis_obj, ColumnSetAnalysis)
        return analysis_obj.columns_for_update

    def _create_values(self, column, platforms, language, is_where_clause):
        assert isinstance(column, ColumnAnalysis)
        is_required = column.update_required

        if is_where_clause:
            values = column.update_restrictions
        else:
            # Can be None
            values = [column.update_value]
            if values[0].arguments is None or len(values[0].arguments) <= 0:
                is_required = True

        ret = []
        for v in values:
            if v is None:
                # Add the value directly
                ret.append(InputValue.create_specified(column, is_required,
                           is_where_clause, None, [],
                           # FIXME this is specific to PHP prepared statements
                           ':' + column.sql_name, [column.sql_name]))
            else:
                assert isinstance(v, AbstractProcessedConstraint)
                # Updates currently have either required values or default
                # values, not both.

                if is_required:
                    ret.append(InputValue.create_specified_constraint(
                        column, True, is_where_clause, v.constraint, platforms,
                        language))
                else:
                    ret.append(InputValue.create_default_constraint(
                        column, False, is_where_clause, v.constraint, platforms,
                        language))
        return ret


class CreateQuery(UpdateCreateQuery):
    """
    Handles the creation of the parts of the insert query.

    The update query has 3 sections: the required parameters (must be supplied
    by the user), the optional parameters (may be provided, but doesn't have to,
    and can have a value (code or sql) if the user didn't give it),
    and the constraints.
    """

    def __init__(self, analysis_obj, platforms, language):
        UpdateCreateQuery.__init__(self, analysis_obj, platforms, language)
        assert isinstance(analysis_obj, ColumnSetAnalysis)

        # names of columns that the database creates.
        # There can be only one of these.
        self.generated_column_name = None

        for c in analysis_obj.columns_analysis:
            assert isinstance(c, ColumnAnalysis)
            if c.auto_gen:
                if self.generated_column_name is not None:
                    raise Exception("multiple auto-generated column values")
                self.generated_column_name = c.sql_name

    def _get_columns_for(self, analysis_obj):
        assert isinstance(analysis_obj, ColumnSetAnalysis)
        return analysis_obj.columns_for_create

    def _create_values(self, column, platforms, language, is_where_clause):
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
        for v in values:
            # Create values are ALWAYS required.

            if v is None:
                # Add the value directly
                # FIXME this is specific to PHP prepared statements
                ret.append(InputValue.create_specified(
                    column, is_required, is_where_clause, None, [],
                    ':' + column.sql_name, [column.sql_name]))
            else:
                assert isinstance(v, AbstractProcessedConstraint)

                ret.append(InputValue.create_specified_constraint(
                    column, True, is_where_clause, v.constraint, platforms,
                    language))
        return ret
