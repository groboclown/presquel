"""
Converter for MySql
"""

from .converter import (PrepSqlConverter)
from .php import (escape_php_string)
from ..model.base import (SqlSet, SqlArgument)

class MySqlPrepSqlConverter(PrepSqlConverter):
    def __init__(self, language, platforms):
        PrepSqlConverter.__init__(self, language, platforms)


    def _generate_code_for_collection_arguments(self, output_variable, sql_set,
            sql_bits):
        """
        Generates source code for a SqlSet.  Standard implementations should
        take the output_variable as the pending sql string variable, and
        replace the collection variables.
        """
        assert isinstance(output_variable, str)
        assert isinstance(sql_set, SqlSet)
        assert isinstance(sql_bits, list)

        if self.language == 'php':
            code = [
                '        ' + output_variable + ' = "";'
            ]
            for stype, bit in sql_bits:
                if stype == 0:
                    assert isinstance(bit, str)
                    code.append('        ' + output_variable + ' .= "' +
                        escape_php_string(bit) + '";')
                else:
                    assert isinstance(bit, SqlArgument)
                    # NOTE: this is MySql + PHP, so we know that the
                    # parameter is in the form ':name', so we can knowingly
                    # add the index outside the parameter generation.
                    code.extend([
                        '        $tmpLoopArray = array();',
                        '        $tmpLoopIndex = 0;',
                        '        foreach ($' + bit.name + ' as $tmpLoop) {',
                        '            $tmpLoopArray[] = "' + escape_php_string(
                            self._generate_sql_parameter(bit.name)) +
                            '".str($tmpLoopIndex);',
                        '            $data["' + escape_php_string(bit.name) +
                            '".str($tmpLoopIndex)] = $tmpLoop;',
                        '            $tmpLoopIndex += 1;',
                        '        }',
                        '        ' + output_variable +
                            ' .= join(", ", $tmpLoopArray);',
                    ])
            return code
        raise Exception("unsupported language: " + self.language)

