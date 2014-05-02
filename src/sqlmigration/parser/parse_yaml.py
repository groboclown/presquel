
from .base import SchemaParser
import yaml


class YamlSchemaParser(SchemaParser):
    def parse(self, source, stream):
        return self._parse_dict(source, yaml.load(stream))
