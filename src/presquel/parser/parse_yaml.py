
from .base import SchemaParser
import yaml


class YamlSchemaParser(SchemaParser):
    def _parse_stream(self, source, stream):
        return self._parse_dict(yaml.load(stream))
