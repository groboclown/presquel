__author__ = 'Groboclown'

import sys

req_version = (3, 1)
cur_version = sys.version_info
assert cur_version >= req_version, "You must run this with Python 3"


from .parser import load_package
from .schemagen import get_generator

from . import model
from . import codegen
