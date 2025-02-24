import time

from medgen.api import ClinVarDB
from text2gene import LVG


hgvs_examples = ClinVarDB().fetchall('select * from samples_vus')

print()
print('%i HGVS examples found' % len(hgvs_examples))
print()

def dmesg(hgvs_text, msg):
    print('[%s] <%i> %s' % (hgvs_text, time.time(), msg))

for entry in hgvs_examples:
    hgvs_text = entry['HGVS']
    dmesg(hgvs_text, 'collecting')
    try:
        lex = LVG(hgvs_text)
        dmesg(hgvs_text, '%r' % lex.variants)
    except Exception as error:
        dmesg(hgvs_text, '%r' % error)
    dmesg(hgvs_text, 'done')

