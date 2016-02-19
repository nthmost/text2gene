from __future__ import absolute_import, print_function, unicode_literals

import hgvs.dataproviders.uta as uta
import hgvs.parser
import hgvs.variantmapper

from .exceptions import IncompleteEdit

hgvs_parser = hgvs.parser.Parser()

uta = hgvs.dataproviders.uta.connect()
mapper = hgvs.variantmapper.EasyVariantMapper(uta)


def _seqvar_map_func(in_type, out_type):
    func_name = '%s_to_%s' % (in_type, out_type)
    return getattr(mapper, func_name)

class HgvsComponents(object):

    def __init__(self, seqvar=None, **kwargs):
        if seqvar:
            self.seqtype, self.edittype, self.ref, self.pos, self.alt = self.parse(seqvar)
        else:
            self.seqtype = kwargs.get('seqtype', None)
            self.edittype = kwargs.get('edittype', None)
            self.ref = kwargs.get('ref', None)
            self.pos = kwargs.get('pos', None)
            self.alt = kwargs.get('alt', None)

    @staticmethod
    def parse(seqvar):
        """ return tuple of sequence variant components as 
        (seqtype, edittype, ref, pos, alt)
        """
        seqtype = seqvar.type
        try:
            ref = seqvar.posedit.edit.ref
        except AttributeError:
            # seqvar has incomplete edit information. fail out.
            raise IncompleteEdit('SequenceVariant %s edit information incomplete or invalid.' % seqvar.ac)

        alt = seqvar.posedit.edit.alt
        edittype = seqvar.posedit.edit.type.upper()

        if seqvar.posedit.pos.end != seqvar.posedit.pos.start:
            pos = '%s_%s' % (seqvar.posedit.pos.start, seqvar.posedit.pos.end)
        else:
            pos = '%s' % seqvar.posedit.pos.start

        return seqtype, edittype, ref, pos, alt

        


class HgvsLVG(object):

    def __init__(self, hgvs_text):
        self.hgvs_text = hgvs_text

        # use the hgvs library to get us some info about this HGVS string.
        self.seqvar = self.parse(hgvs_text)

        # fill in all the different ways to talk about this variant in each sequence type.
        self.variants = {'g': [], 'c': [], 'n': [], 'p': []}
        self.variants[self.seqvar.type] = [self.seqvar]

        for this_type, value in list(self.variants.items()):
            if value == []:
                self.variants[this_type] = [_seqvar_map_func(self.seqvar.type, this_type)(self.seqvar)]

        if self.variants['g']:
            self.transcripts = self.get_transcripts(self.variants['g'][0])

    @staticmethod
    def get_transcripts(var_g):
        return mapper.relevant_transcripts(var_g)

    @staticmethod
    def parse(hgvs_text):
        return hgvs_parser.parse_hgvs_variant(hgvs_text)

    def __str__(self):
        out = 'HGVS input: %s\n' % self.hgvs_text
        out += '%r' % self.seqvar
        return out


if __name__=='__main__':
    import sys
    try:
        hgvs_text = sys.argv[1]
    except IndexError:
        print('Supply hgvs text as argument to this script.')
        sys.exit()

    hgvs_obj = HgvsLVG(hgvs_text) 

    print(hgvs_obj)

    # Turn off IPython deprecation warnings, ugh
    import warnings
    def fxn():
        warnings.warn('deprecated', DeprecationWarning)
    
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        fxn()

    print()
    print(HgvsLVG.get_components(hgvs_obj.seqvar))
    print()

    for vartype in list(hgvs_obj.variants.keys()):
        print(hgvs_obj.variants[vartype])
