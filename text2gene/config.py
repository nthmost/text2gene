from __future__ import absolute_import, print_function

import os
from configparser import ConfigParser

PKGNAME = 'skeleton'
default_cfg_dir = os.path.join(os.getcwd(), 'etc')
CFGDIR = os.getenv('%s_CONFIG_DIR' % PKGNAME, default_cfg_dir)
DEBUG = bool(os.getenv('%s_DEBUG' % PKGNAME, False))
ENV = os.getenv('%s_ENV' % PKGNAME, 'dev')

####
import logging
log = logging.getLogger(PKGNAME)
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)
####
    
log.debug('%s-services config dir: %s' % (PKGNAME, CFGDIR))
log.debug('%s-services env: %s' % (PKGNAME, ENV))

configs = [os.path.join(CFGDIR, x) for x in os.listdir(CFGDIR) if x.find(ENV+'.ini') > -1]

CONFIG = ConfigParser()
CONFIG.read(configs)

