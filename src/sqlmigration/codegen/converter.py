"""
Handles the conversion of SQL into code or straight up SQL.
"""

from ..model.base import (SqlArgument, SqlSet, LanguageSet)
from ..model.schema import (SqlConstraint, LanguageConstraint)
from .sql import (InputValue)




class PrepSqlConverter(object):
    """
    Manages the conversion of a model SqlArgument into a prepared statement
    string argument.
    """
    def __init__(self, language, platforms):
        object.__init__(self)
        assert isinstance(language, str)
        assert isinstance(platforms, list) or isinstance(platforms, tuple)
        for plat in platforms:
            assert isinstance(plat, str)
        self.__language = language
        self.__platforms = tuple(platforms)

    @property
    def language(self):
        """
        Software language for which this generates SQL

        :return str:
        """
        return self.__language

    @property
    def platforms(self):
        """
        List of SQL platforms tha this converter uses.

        :return list(str):
        """
        return self.__platforms

    def generate_code(self, output_variable, arg):
        """
        Creates the language-specific code related to this SqlSet or
        InputValue or Constraint or LanguageSet.
        """
        assert isinstance(output_variable, str)
        if isinstance(arg, SqlSet):
            return self._generate_code_for_sql_set(output_variable, arg)
        if isinstance(arg, SqlConstraint):
            return self._generate_code_for_sql_set(output_variable, arg.sql)
        if isinstance(arg, LanguageSet):
            return self._generate_code_for_lang_set(output_variable, arg)
        if isinstance(arg, LanguageConstraint):
            return self._generate_code_for_lang_set(output_variable, arg.code)
        assert False, "Incorrect type for arg"

    def generate_sql(self, arg):
        """
        Creates the SQL that will be escaped and inserted into the correct
        part of the code, for this SqlSet or InputValue or Constraint
        """
        if isinstance(arg, SqlSet):
            return self._generate_sql_for_sql_set(arg)
        if isinstance(arg, SqlConstraint):
            return self._generate_sql_for_sql_set(arg.sql)
        if isinstance(arg, LanguageConstraint):
            # No-op
            return ''
        if isinstance(arg, LanguageSet):
            return ''
        assert False, "Incorrect type for arg"

    def _generate_code_for_lang_set(self, output_variable, lang):
        assert isinstance(LanguageSet, lang)
        code = lang.get_for_language(lang)
        code = code.replace("{out}", output_variable)
        return code

    def _generate_code_for_sql_set(self, output_variable, sql_set):
        """
        Generates source code for a SqlSet.  Standard implementations should
        take the output_variable as the pending sql string variable, and
        replace the collection variables.
        """
        # for arg in sql_set.collection_arguments:
        #    assert isinstance(arg, SqlArgument)
        #    assert arg.is_collection is True
        #    sql = self.
        raise NotImplementedError()

    def _generate_sql_for_sql_set(self, sql_set):
        """
        Generates the SQL for a SqlSet
        """
        assert isinstance(sql_set, SqlSet)
        sql = sql_set.get_for_platform(self.platforms)
        if sql is None:
            raise Exception("platform not supported: " + str(self.platforms))
        for arg in sql_set.simple_arguments:
            assert isinstance(arg, SqlArgument)
            assert arg.is_collection is False
            sql = sql.replace('{' + arg.name + '}',
                self._generate_sql_parameter(arg.name))

        # Default implementation does not handle collection arguments; those
        # are assumed to be handled by code.
        return sql

    def _generate_sql_parameter(self, arg_name):
        """
        Creates a SQL string named "parameterized" value.
        """
        assert isinstance(arg_name, str)
        return ':' + arg_name
