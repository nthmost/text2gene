from __future__ import absolute_import, print_function, unicode_literals

import logging

import hgvs.dataproviders.uta as uta
import hgvs.parser
import hgvs.variantmapper
from hgvs.exceptions import HGVSDataNotAvailableError

from .hgvs_components import HgvsComponents

log = logging.getLogger('hgvs.lvg')

hgvs_parser = hgvs.parser.Parser()

#UTACONNECTION = 'postgresql://uta_admin:anonymous@192.168.1.3/uta_20150903/'
#uta = hgvs.dataproviders.uta.connect(UTACONNECTION + '/' + _uta_schema, pooling=True)
#uta = hgvs.dataproviders.uta.connect(UTACONNECTION, pooling=True)

uta = hgvs.dataproviders.uta.connect()
mapper = hgvs.variantmapper.EasyVariantMapper(uta)


def _seqvar_map_func(in_type, out_type):
    func_name = '%s_to_%s' % (in_type, out_type)
    return getattr(mapper, func_name)


def variant_to_gene_name(seqvar):
    """
    Get HUGO Gene Name (Symbol) for given sequence variant object.

    Input seqvar must be of type 'n', 'c', or 'p'.

    :param variant: hgvs.SequenceVariant
    :return: string gene name (or None if not available).
    """
    if seqvar.type in ['n', 'c', 'p']:
        try:
            tx_identity = uta.get_tx_identity_info(seqvar.ac)
        except HGVSDataNotAvailableError:
            return None

        if tx_identity is not None:
            return tx_identity[-1]
        else:
            return None
    else:
        return None


def _seqvar_to_seqvar(seqvar, base_type, new_type):
    if base_type == new_type:
        return None

    if base_type == 'p':
        return None

    if new_type == 'p' and base_type == 'g':
        return None

    try:
        return _seqvar_map_func(base_type, new_type)(seqvar)
    except NotImplementedError:
        return None
    except HGVSDataNotAvailableError as error:
        log.debug('%r' % error)
        return None

        
class HgvsLVG(object):

    def __init__(self, hgvs_text, **kwargs):
        self.hgvs_text = hgvs_text

        # use the hgvs library to get us some info about this HGVS string.
        self.seqvar = self.parse(hgvs_text)

        # initialize transcripts list
        self.transcripts = set(kwargs.get('transcripts', []))

        # fill in all the different ways to talk about this variant in each sequence type.
        self.variants = {'g': dict(), 'c': dict(), 'n': dict(), 'p': dict()}
        self.variants[self.seqvar.type][str(self.seqvar)] = self.seqvar

        if self.seqvar.type == 'p':
            # no backreference to 'c','g','n' possible from a 'p' seqvar
            self.variants['p'] = [self.seqvar]

        if self.variants['c']:
            # attempt to derive all 4 types of SequenceVariants from 'c'.
            for this_type, value in list(self.variants.items()):
                new_seqvar = _seqvar_to_seqvar(self.seqvar, self.seqvar.type, this_type)
                if new_seqvar:
                    self.variants[this_type][str(new_seqvar)] = new_seqvar

        # Now that we have a 'g', collect all available transcripts.
        if self.variants['g']:
            for var_g in list(self.variants['g'].values()):
                for trans in self.get_transcripts(var_g):
                    self.transcripts.add(trans)

        # In the case of starting with a 'g' type...
        if self.seqvar.type == 'g' and self.transcripts:
            # we still need to collect 'c' and 'n' variants
            for trans in self.transcripts:
                var_c = mapper.g_to_c(self.seqvar, trans)
                if var_c:
                    self.variants['c'][str(var_c)] = var_c
                var_n = mapper.g_to_n(self.seqvar, trans)
                if var_n:
                    self.variants['n'][str(var_n)] = var_n

        # With a list of transcripts, we can do g_to_c and g_to_n
        if self.transcripts:
            for trans in self.transcripts:
                for var_g in list(self.variants['g'].values()):
                    # Find all available 'c'
                    if not trans.startswith('NR'):
                        new_seqvar = mapper.g_to_c(var_g, trans)
                        if new_seqvar:
                            self.variants['c'][str(new_seqvar)] = new_seqvar

                    # Find all available 'n'
                    new_seqvar = mapper.g_to_n(var_g, trans)
                    if new_seqvar:
                        self.variants['n'][str(new_seqvar)] = new_seqvar

        # map all newly found 'c' to 'p'
        for var_c in list(self.variants['c'].values()):
            new_seqvar = _seqvar_to_seqvar(var_c, 'c', 'p')
            if new_seqvar:
                self.variants['p'][str(new_seqvar)] = new_seqvar

        # find out the gene name of this variant.
        self._gene_name = None

    @property
    def gene_name(self):
        if self._gene_name is None:     # and self.seqvar.type != 'p':
            if self.variants['c']:
                chosen_one = list(self.variants['c'].values())[0]
            elif self.variants['n']:
                chosen_one = list(self.variants['n'].values())[0]
            else:
                chosen_one = list(self.variants['p'].values())[0]
            self._gene_name = variant_to_gene_name(chosen_one)
        return self._gene_name

    @staticmethod
    def get_transcripts(var_g):
        return mapper.relevant_transcripts(var_g)

    @staticmethod
    def parse(hgvs_text):
        return hgvs_parser.parse_hgvs_variant(hgvs_text)

    def to_dict(self, with_gene_name=True):
        """Returns contents of object as a 2-level dictionary.

        Supply with_gene_name = True [default: True] to return gene_name as well.

        (gene_name is a lazy-loaded magic attribute, and may take a second or two).
        """
        outd = { 'variants': {},
                 'transcripts': list(self.transcripts),
                 'seqvar': self.seqvar,
                 'hgvs_text': self.hgvs_text,
               }

        if with_gene_name:
            outd['gene_name'] = self.gene_name

        # turn each seqvar dictionary into just a list of its values (the seqvar objects).
        for seqtype, seqvar_dict in (self.variants.items()):
            outd['variants'][seqtype] = list(seqvar_dict.values())

        return outd

    def __str__(self):
        out = 'HGVS input: %s\n' % self.hgvs_text
        out += '%r' % self.seqvar
        return out



### API Convenience Functions

Variant = HgvsLVG.parse


if __name__=='__main__':
    import sys
    try:
        hgvs_text = sys.argv[1]
    except IndexError:
        print('Supply hgvs text as argument to this script.')
        sys.exit()

    hgvs_obj = HgvsLVG(hgvs_text) 

    print(hgvs_obj)

    print()
    print(HgvsComponents(hgvs_obj.seqvar))
    print()

    for vartype in list(hgvs_obj.variants.keys()):
        print(hgvs_obj.variants[vartype])

    print()
    print(hgvs_obj.gene_name)
