
"""
Tools to help in the generation of PHP source files.
"""


def escape_php_string(s):
    """

    :param s: the text, as a string
    :return: escaped text, ready for insertion into a PHP string.
    """

    return (s.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').
        replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'))
