
from .base import SchemaParser
from yaml import load as load_yaml


class YamlSchemaParser(SchemaParser):
    def _parse_stream(self, stream):
        return self._parse_dict(load_yaml(stream))
