from __future__ import absolute_import, unicode_literals

from flask import Blueprint, render_template, redirect, request, abort

from metapub import PubMedFetcher

from metavariant import VariantLVG, VariantComponents
from metavariant.exceptions import CriticalHgvsError, NCBIRemoteError
from metavariant.utils import strip_gene_name_from_hgvs_text

from .utils import HTTP200, get_hostname, restrict_by_ip
from .config import ENV, CONFIG, PKGNAME

#from .report_utils import get_clinvar_tables_containing_variant
from .lsdb.lovd import get_lovd_url
from .api import LVG, CitationTable, GeneInfo, ClinVarInfo

fetch = PubMedFetcher()

base = Blueprint('base', __name__, template_folder='templates')

HGVS_SAMPLES = ['NM_194248.1:c.158C>T',
                'NM_006206.4:c.1700C>T',
                'NM_001126115.1:c.318T>G',
                'NM_005228.3:c.2240_2257del18'
                ]

@base.route('/')
def home():
    return render_template('demo.html')


@base.route('/about')
def about():
    return render_template('about.html')


@base.route('/who')
def who():
    return render_template('who.html')


@base.route('/demo')
def demo():
    return render_template('demo.html')


@base.route('/faq')
def faq():
    return render_template('faq.html')


@base.route('/amino', methods=['GET','POST'])
@restrict_by_ip
def amino_change_query(pos='', ref='', alt=''):
    return render_template('demo.html')


@base.route('/variant', methods=['POST'])
@base.route('/variant/<hgvs_text>', methods=['GET'])
@base.route('/query', methods=['POST'])
@base.route('/query/<hgvs_text>', methods=['GET'])
@restrict_by_ip
def query(hgvs_text=''):
    """ Runs all of the relevant search queries after producing a lex object from input hgvs_text """

    # Normalize all requests to a GET with hgvs_text having no gene name.
    if request.method == 'POST':
        hgvs_text = strip_gene_name_from_hgvs_text(request.form.get('hgvs_text', '').strip())
        return redirect('/query/%s' % hgvs_text, code=302)
    else:
        if strip_gene_name_from_hgvs_text(hgvs_text) != hgvs_text:
            return redirect('/query/%s' % strip_gene_name_from_hgvs_text(hgvs_text), code=302)
        hgvs_text = hgvs_text.strip()

    try:
        lex = LVG(hgvs_text)
    except CriticalHgvsError as error:
        return render_template('demo.html', error_msg='%r' % error)

    # GENE INFO: nice info to have at hand (e.g. medgen url) if we know the gene name for this variant.
    if lex.gene_name:
        gene_info = GeneInfo(gene_name=lex.gene_name)
    else:
        gene_info = None

    # CLINVAR INFO: nice info to have at hand if we can look up the variation ID for given hgvs_text.
    clinvar_info = ClinVarInfo(hgvs_text)

    # CITATION TABLE: handles all the heavy lifting of hgvs2pmid lookups and arrange citations by PMID.
    citation_table = CitationTable(lex)

    # LOVD URL: link to search in a relevant LOVD instance, if we know of one.
    comp = VariantComponents(lex.seqvar)
    lovd_url = get_lovd_url(lex.gene_name, comp)

    return render_template('query.html', lex=lex, lovd_url=lovd_url, citation_table=citation_table,
                           clinvar = clinvar_info, gene=gene_info,
                           found_in_clinvar_example_tables=None)
                           # found_in_clinvar_example_tables=get_clinvar_tables_containing_variant(hgvs_text))


@base.route('/examples')
def examples():
    api_version = CONFIG.get('api', 'latest_version')
    return render_template('examples.html', hgvs_samples=HGVS_SAMPLES, api_version=api_version)


@base.route('/OK')
def OK():
    return HTTP200({ 'service': '%s' % PKGNAME, 
                     'ENV': '%s' % ENV,
                     'hostname': '%s' % get_hostname(),
                     'api_latest_version': CONFIG.get('api', 'latest_version'), 
                     'api_supported_versions': CONFIG.get('api', 'supported_versions'),
                   })
