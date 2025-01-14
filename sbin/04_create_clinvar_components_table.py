from __future__ import absolute_import, print_function

from metavariant import Variant, VariantComponents
from metavariant.exceptions import RejectedSeqVar, CriticalHgvsError
from medgen.db.clinvar import ClinVarDB

from aminosearch.sqldata import SQLData
from aminosearch.config import get_process_log

import re
import subprocess

SOURCE_TABLENAME = 'clinvar.t2g_variant_summary'
TARGET_TABLENAME = 'clinvar.t2g_hgvs_components'

# HGVS regex: https://regex101.com/r/yI1kR6/1
re_hgvs = re.compile('(?P<prefix>N[A-Z])_(?P<transcript>\d+\.\d+)(\((?P<symbol>\w+)\))?\:(?P<edit>.*?)\s')

# LRG regex: https://regex101.com/r/bT1gW3/2
#re_lrg = re.compile('(?P<prefix>LRG)_(?P<position>\w+)\:(?<edit>[a-z]\.\w+)')

log = get_process_log('logs/clinvar_components_table.log')

UNUSABLE = 0
GOOD = 0

DB_ERROR_FILE = open('logs/clinvar_components_db_errors.txt', 'w')

def write_db_error(msg, err_obj):
    DB_ERROR_FILE.write('%r: %s\n' % (err_obj, msg))
    DB_ERROR_FILE.flush()

def components_or_None(hgvs_p):
    try:
        comp = VariantComponents(Variant(hgvs_p))
        if comp.ref != '':
            return comp
    except (TypeError, RejectedSeqVar, CriticalHgvsError):
        # either the hgvs_p did not parse (Variant returned None) or it has incomplete edit info.
        pass
    return None

def seqvar_or_None(entry):
    if entry is None:
        return None

    # basic string cleaning
    entry = entry.strip()
    # beware the pesky N-dash in at least 1 observed ClinVar db entry.
    entry = entry.replace('\u2013', '-')

    hgvs_text = ''

    match = re_hgvs.match(entry)
    if match:
        stuff = match.groupdict()
        hgvs_text = stuff['prefix'] + '_' + stuff['transcript'] + ':' + stuff['edit']

    # TODO: LRG 
    else:
        return None

    try:
        return Variant(hgvs_text)
    except (CriticalHgvsError, TypeError):
        # empty or broken
        return None

def lvg_or_None(seqvar):
    try:
        return LVG(seqvar)
    except Exception as error:
        write_db_error('Could not create LVG object for %s' % seqvar, error)
        log.debug('ERROR: %r' % error)
        log.info('Could not create LVG object for %s' % seqvar)
        return None

def process_row(db, dbrow):
    """ For each column in the row that might contain an HGVS string -- namely:
        * variant_name
        * HGVS_p
        * HGVS_c

    ...do the following actions:
        * if variant_name or HGVS_c, make an LVG. If both exist, make an lvg from HGVS_c (preferentially).
            * for each seqvar, add a row to the database with '%s' % seqvar, PMID, VariantComponents --> Ref,Alt,Pos
        * if HGVS_p, see if it exists in the LVG object (in hgvs_p). 

            * if not: try to make a VariantComponents object. add new row if comp is not None.

    :param dbrow: (dict) one row from t2g_variant_summary table.
    :return: list of VariantComponents successfully added to the database (or empty list)
    """

    added_components = []

    variants = {'c': [], 'g': [], 'n': []}

    for option in ['variant_name']:         #, 'HGVS_c']:
        seqvar = seqvar_or_None(dbrow[option])
        if seqvar:
            variants[seqvar.type].append(seqvar)

    # use the first usable variant to construct an LVG for this variant.
    lex = None
    for seqtype in ['c', 'g', 'n']:
        if variants[seqtype]:
            seqvar = variants[seqtype][0]
            print('[%s] Using %s to build LVG' % (dbrow['variant_name'], seqvar))
            lex = lvg_or_None(seqvar)
            if lex:
                break

    # collect a unique set of protein variants stripped of parentheses.
    hgvs_ps = set()
    #comp = components_or_None(dbrow['HGVS_p'])
    #if comp:
        # treat "uncertain" protein effects as unneeded duplicates of the "certain" ones.
    #    hgvs_ps.add(('%s' % Variant(dbrow['HGVS_p'])).replace(')','').replace('(',''))

    # add non-p-vars to the database
    if lex:
        for item in lex.hgvs_p:
            hgvs_ps.add(item.replace(')','').replace('(',''))
        
        for seqtype in ['c', 'g', 'n']:
            for seqvar in lex.variants[seqtype].values():
                comp = components_or_None(seqvar)
                if comp:
                    if add_components_to_row(db, dbrow, comp):
                        added_components.append(comp)

    # and now add the proteins
    for hgvs_p in hgvs_ps:
        comp = components_or_None(Variant(hgvs_p))
        if comp:
            if add_components_to_row(db, dbrow, comp):
                added_components.append(comp)

    return added_components


def print_dbrow_with_components(dbrow, qualifier):
    print("""[{variant_name}] (VariationID: {VariationID}) {qual}""".format(qual=qualifier.upper(), **dbrow))


def add_components_to_row(db, dbrow, comp):
    print('ADD:')
    try:
        fvdict = comp.to_mysql_dict()
        fvdict['HGVS'] = '%s' % comp.seqvar
        fvdict['PMID'] = dbrow['PMID']
        fvdict['Symbol'] = dbrow['Symbol']
        fvdict['GeneID'] = dbrow['GeneID']
        fvdict['VariationID'] = dbrow['VariationID']

        print(fvdict)

        db.insert(TARGET_TABLENAME, fvdict)

        print_dbrow_with_components(dbrow, 'added')
        print()
        return True

    except AttributeError as error:
        print(error)
        print()
        return False


def main():
    global UNUSABLE
    global GOOD

    db = ClinVarDB()
    
    # hello, are you there MySQL? It's me, python.
    db.ping()
    
    print('(Re)creating clinvar component table', TARGET_TABLENAME)

    db.drop_table(TARGET_TABLENAME)
    db.execute("call log('components', 'creating "+TARGET_TABLENAME+" table')")
    db.execute('''create table '''+TARGET_TABLENAME+''' (
        id int(11) primary key auto_increment,
        VariationID int(11),
        hgvs_text varchar(255),
        PMID int(11) default null,
        GeneID int(11) default null,
        Symbol varchar(20) default null,
        Ref varchar(10) default null,
        Pos int(11) default null,
        Alt varchar(10) default null,
        EditType varchar(25) default null,
        SeqType varchar(10) default null)''')

    log.info('Rebuilding %s', TARGET_TABLENAME)

    log.info('Creating unique index on PMID-hgvs_text')
    db.execute('ALTER TABLE '+TARGET_TABLENAME+' ADD UNIQUE INDEX pmid_hgvs (PMID, hgvs_text)')

    try:
        res = db.fetchrow('select count(*) as cnt from %s' % SOURCE_TABLENAME)
    except Exception as error:
        print(error)
        log.debug('%r' % error)
        sys.exit()

    log.info('Rows in %s: %i' % (SOURCE_TABLENAME, res['cnt']))

    rows = db.fetchall('select * from '+SOURCE_TABLENAME+' order by rand()')

    count = 0
    total_added = 0
    for row in rows:
        count += 1
        print(count, '/', res['cnt'], ':', row['variant_name'])
        results = process_row(db, row)
        if len(results) == 0:
            UNUSABLE += 1
        else:
            GOOD += 1
        total_added += len(results)

    return len(rows), total_added


if __name__=='__main__':

    dbtotal, added = main()
    print('@@@ FINISHED!!!!')
    print()
    print('good:', GOOD)
    print('unusable:', UNUSABLE)
    print('total in DB:', dbtotal)
    print('component rows added:', added)
    print('-----------')
    print()
    print('Sourcing sbin/clinvar_components_index.sql...')

    cmd = 'mysql -u medgen -pmedgen -D clinvar < sbin/05_clinvar_components_index.sql'

    print(subprocess.call(cmd, shell=True))


