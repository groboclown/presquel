"""
A framework for generating files for a single SQL object.
"""

from .analysis import (ColumnSetAnalysis)
from .converter import (PrepSqlConverter)
from ..model.schema import (ExtendedSql)
import os



class GenConfig(object):
    def __init__(self, analysis_obj, output_dir = None, platforms = None,
            prep_sql_converter = None):
        object.__init__(self)

        assert isinstance(analysis_obj, ColumnSetAnalysis)
        self.analysis_obj = analysis_obj
        self.output_dir = output_dir
        self.platforms = platforms
        self.prep_sql_converter = prep_sql_converter
        self.fail_if_file_exists = True

        # FIXME pull from Python built-ins
        self.line_separator = '\n'


    def validate(self):
        assert self.output_dir is not None
        assert isinstance(self.analysis_obj, ColumnSetAnalysis)
        assert isinstance(self.output_dir, str)
        assert (isinstance(self.platforms, list) or
                isinstance(self.platforms, tuple))
        assert len(self.platforms) > 0
        assert isinstance(self.prep_sql_converter, PrepSqlConverter)



class LanguageGenerator(object):
    """
    An abstract class that handles the language-specific aspects of translating
    the SQL specific aspects.
    """
    def __init__(self):
        object.__init__(self)

    def generate_filename(self, config):
        """
        Generate the filename that will be used for the given analysis_obj.
        This should be relative to the base directory (not passed in).

        :param config GenConfig:
        """
        raise NotImplementedError()

    def generate_header(self, config):
        """
        Create the boiler plate involved in the file header.

        Returns an array that will be joined together with the correct
        OS line separator.
        """
        raise NotImplementedError()

    def generate_read(self, config):
        raise NotImplementedError()

    def generate_create(self, config):
        raise NotImplementedError()

    def generate_update(self, config):
        raise NotImplementedError()

    def generate_delete(self, config):
        raise NotImplementedError()

    def generate_extended_sql(self, config, extended_sql):
        raise NotImplementedError()

    def generate_extended_sql_wrapper(self, config, extended_sql):
        raise NotImplementedError()

    def generate_validations(self, config):
        raise NotImplementedError()

    def generate_footer(self, config):
        raise NotImplementedError()



class FileGen(object):
    """
    Handles the generation of the output file.
    """
    def __init__(self, lang_gen):
        object.__init__(self)

        assert isinstance(lang_gen, LanguageGenerator)
        self.lang_gen = lang_gen


    def generate_file(self, config):
        """
        Create the output file for the given analysis object configuration.
        """
        assert isinstance(config, GenConfig)
        config.validate()

        file_name = os.path.join(config.output_dir,
             self.lang_gen.generate_filename(config))
        if os.path.exists(file_name) and config.fail_if_file_exists:
            raise Exception("Will not overwrite " + file_name)

        with open(file_name, 'w') as out:
            self.__output(config, out, self.lang_gen.generate_header(config))

            self.__output(config, out, self.generate_read(config))

            if not config.analysis_obj.is_read_only:
                self.__output(config, out, self.generate_create(config))
                self.__output(config, out, self.generate_update(config))
                self.__output(config, out, self.generate_delete(config))

            self.__output(config, out, self.generate_extended_sql(config))

            self.__output(config, out, self.generate_validations(config))

            self.__output(config, out, self.lang_gen.generate_footer(config))

    def generate_read(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)
        return self.lang_gen.generate_read(config)

    def generate_create(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)
        return self.lang_gen.generate_create(config)

    def generate_update(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)
        return self.lang_gen.generate_update(config)

    def generate_delete(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)
        return self.lang_gen.generate_delete(config)

    def generate_extended_sql(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)

        ret = []
        for extended_sql in config.analysis_obj.schema.extended_sql:
            assert isinstance(extended_sql, ExtendedSql)
            if extended_sql.is_wrapper:
                ret.extend(self.lang_gen.generate_extended_sql_wrapper(
                    config, extended_sql))
            else:
                ret.extend(self.lang_gen.generate_extended_sql(
                    config, extended_sql))
        return ret

    def generate_validations(self, config):
        """
        :return: a list of strings, one per line for the source
        """
        assert isinstance(config, GenConfig)

        # FIXME split into table validations (read & write), read validations,
        # and write validations.

        return self.lang_gen.generate_validations(config)

    def __output(self, config, out, lines):
        # FIXME test for iterable instead?
        assert isinstance(config, GenConfig)
        assert isinstance(lines, tuple) or isinstance(lines, list)
        out.writelines(config.line_separator.join(lines))

