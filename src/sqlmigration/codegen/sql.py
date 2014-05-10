
"""
Helper utility for the generation of SQL from the analysis, and for modifying
the strings for appropriate insertion into generated code.
"""

from .analysis import (ProcessedForeignKeyConstraint, ColumnAnalysis,
                       ColumnSetAnalysis, AbstractProcessedConstraint)
from ..model import (SqlConstraint, SqlSet, Table, View, Column)


class ReadQueryData(object):
    def __init__(self, analysis_obj, platforms):
        assert isinstance(analysis_obj, ColumnSetAnalysis)

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
                assert isinstance( qr, AbstractProcessedConstraint)
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
