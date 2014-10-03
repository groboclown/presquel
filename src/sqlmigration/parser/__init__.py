__author__ = 'Groboclown'

from .base import SchemaParser
from .parse_json import *
from .parse_xml import *
from .parse_yaml import *

JSON_PARSER = JsonSchemaParser()
XML_PARSER = XmlSchemaParser()
YAML_PARSER = YamlSchemaParser()

PARSERS = (JSON_PARSER, XML_PARSER, YAML_PARSER)
PARSERS_BY_EXTENSION = {
    '.xml': XML_PARSER,
    '.json': JSON_PARSER,
    '.yaml': YAML_PARSER
}

# This needs to be defined after the parsers
from .file_loader import *
