"""
Handles the conversion of SQL into code or straight up SQL.
"""

from ..model.base import (SqlArgument, SqlSet, LanguageSet, SqlString)
from ..model.schema import (SqlConstraint, LanguageConstraint)


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
        if isinstance(arg, SqlArgument):
            if arg.is_collection:
                return ''
            return self._generate_sql_parameter(arg.name)
        assert False, "Incorrect type for arg: " + str(type(arg))

    def _generate_code_for_lang_set(self, output_variable, lang):
        assert isinstance(LanguageSet, lang)
        code = lang.get_for_language(lang)
        code = code.replace("{out}", output_variable)
        return code

    def _generate_code_for_sql_set(self, output_variable, sql_set):
        """
        Generates source code for a SqlSet.  If the SqlSet does not contain
        anything that will generate code, then this MUST return None.

        Default implementation will return None if there is no collection
        argument.
        """
        assert isinstance(sql_set, SqlSet)
        sql = sql_set.get_for_platform(self.platforms)

        # Split the sql into bits for insertion
        sql_bits = [ [ 0, sql ] ]

        has_collections = False

        for arg in sql_set.arguments:
            assert isinstance(arg, SqlArgument)
            new_bits = []
            for stype, bit in sql_bits:
                if stype == 0:
                    match = '{' + arg.name + '}'
                    while bit.count(match) > 0:
                        pos = bit.index(match)

                        if arg.is_collection:
                            has_collections = True
                            new_bits.append([0, bit[0: pos]])
                            new_bits.append([1, arg])
                            bit = bit[pos + len(match):]
                        else:
                            bit = (bit[0:pos] +
                                self._generate_sql_parameter(arg.name) +
                                bit[pos + len(match):])
                    if len(bit) > 0:
                        new_bits.append([0, bit])
                else:
                    new_bits.append([stype, bit])
            sql_bits = new_bits

        if not has_collections:
            return None

        return self._generate_code_for_collection_arguments(output_variable,
            sql_set, sql_bits)

    def _generate_sql_for_sql_set(self, sql_set):
        """
        Generates the SQL for a SqlSet
        """
        assert isinstance(sql_set, SqlSet)
        sql_str = sql_set.get_for_platform(self.platforms)
        if sql_str is None:
            raise Exception("platform not supported: " + str(self.platforms))
        assert isinstance(sql_str, SqlString)
        sql = sql_str.sql
        for arg in sql_set.simple_arguments:
            assert isinstance(arg, SqlArgument)
            if arg.is_collection:
                return None
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

    def _generate_code_for_collection_arguments(self, output_variable,
            sql_set, sql_bits):
        """
        Create the code for the collection arguments.  The "sql_bits" is
        a list of tuples (type id, argument).  The type id is 0 for a
        string argument (straight up SQL text), and 1 for a collection
        SqlArgument.

        :return list(str):
        """
        raise NotImplementedError()
