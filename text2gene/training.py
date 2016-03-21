from __future__ import absolute_import, print_function, unicode_literals

import logging

from pubtatordb import SQLData

from .cached import ClinvarCachedQuery, PubtatorCachedQuery
from .ncbi import NCBIVariantPubmedsCachedQuery, NCBIEnrichedLVGCachedQuery, NCBIHgvsLVG
from .lvg_cached import HgvsLVGCached

log = logging.getLogger('text2gene.experiment')

search_module_map = {'pubtator': PubtatorCachedQuery,
                     'clinvar': ClinvarCachedQuery,
                     'ncbi': NCBIVariantPubmedsCachedQuery,
                    }

lvg_module_map = {'ncbi_enriched': NCBIEnrichedLVGCachedQuery,
                  'hgvs': HgvsLVGCached,
                  'ncbi': NCBIHgvsLVG,
                 }

class Experiment(SQLData):

    def __init__(self, experiment_name, **kwargs):
        self.experiment_name = experiment_name

        self.iteration = kwargs.get('iteration', 0)

        self.lvg_mode = kwargs.get('lvg_mode', 'hgvs')      # or 'ncbi' or 'ncbi_enriched'

        # normalize module names to lowercase to save on the aggravation of case-matching.
        self.search_modules = [item.lower() for item in kwargs.get('search_modules', ['pubtator', 'clinvar', 'ncbi'])]

        self.hgvs_examples_table = kwargs.get('hgvs_examples_table', 'hgvs_examples')
        self.hgvs_examples_db = kwargs.get('hgvs_examples_db', 'clinvar')
        self.hgvs_examples_limit = kwargs.get('hgvs_examples_limit', None)

        # HGVS2PMID cache-backed functions internal to this Experiment
        self.ClinvarHgvs2Pmid = ClinvarCachedQuery(granular=True, granular_table=self.get_table_name('clinvar')).query
        self.PubtatorHgvs2Pmid = PubtatorCachedQuery(granular=True, granular_table=self.get_table_name('pubtator')).query
        self.NCBIHgvs2Pmid = NCBIVariantPubmedsCachedQuery(granular=True, granular_table=self.get_table_name('ncbi')).query

        # setup granular result tables necessary to store our results
        self._setup_tables()

        # set our internal LVG query function based on preference stated in kwargs.
        self.LVG = lvg_module_map[self.lvg_mode]

        super(self.__class__, self).__init__('ncbi_hgvs2pmid')

    def get_table_name(module_name):
        """ Produce a table name for given module_name, based on this Experiment's experiment_name and iteration.

        :return: (str) table name for this experiment and iteration, given module_name
        """
        tname_tmpl = '{expname}_{iteration}_{mod_name}_match'
        return tname_tmpl.format(expname = self.experiment_name, iteration=self.iteration, mod=module_name)

    def _setup_tables(self):
        """ Creates experiment tables in text2gene database for all search_modules used in this Experiment.
        :return: None
        """
        for mod in self.search_modules:
            tablename = self.get_table_name(mod)
            log.debug('Creating table %s', tablename)
            search_module_map[mod]().create_granular_table()

    def _load_examples(self):
        sql = 'select * from {dbname}.{tname}'.format(dbname=self.hgvs_examples_db, tname=self.hgvs_examples_table)
        if self.hgvs_examples_limit:
            sql += ' limit %i' % self.hgvs_examples_limit
        return self.fetchall(sql)

    def run(self):
        for row in self._load_examples():
            hgvs_text = row['hgvs_text'].strip()

            lex = self.LVG(hgvs_text)

            for mod in self.search_modules:
                if mod == 'clinvar':
                    result = self.ClinvarHgvs2Pmid(lex)

                if mod == 'ncbi':
                    result = self.NCBIHgvs2Pmid(lex.hgvs_text)

                if mod == 'pubtator':
                    result = self.PubtatorHgvs2Pmid(lex)

                log.debug(mod, '%r' % result)
