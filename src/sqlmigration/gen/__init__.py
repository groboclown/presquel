__author__ = 'Groboclown'

"""
Contains the process for generating the actual schema based on the
schema version.

These  classes should remain generic enough to be used in many different
applications, meaning that it does not directly interact with the database,
but instead produces scripts that can be used.
"""


from .base import *
from .mysql import *


GENERATORS = (MySqlScriptGenerator(), )


def get_generator(platforms):
    """
    Returns the generator that best matches the given list of platforms.

    :param platforms: list(str) or str
    :return: a list of generators that matches the platforms, which can be
        empty
    """
    if isinstance(platforms, str):
        platforms = [platforms]

    ret = []
    for g in GENERATORS:
        if g.is_platform(platforms):
            ret.append(g)
    return ret

