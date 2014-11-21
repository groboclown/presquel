__author__ = 'Groboclown'

import sys

req_version = (3, 1)
cur_version = sys.version_info
assert cur_version >= req_version, "You must run this with Python 3"


from .parser import load_package
from .schemagen import (get_generator, BranchUpgradeAnalysis)


from . import (model, codegen, schemagen, parser)

VERSION = (0, 2, 0)
VERSION_STR = ".".join([str(ver) for ver in VERSION])
