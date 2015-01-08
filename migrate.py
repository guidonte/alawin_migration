#!/usr/bin/python

import sys
sys.path.insert (0, '/home/guido/src/openerp/server')

import logging
import importlib
import inspect

_logger = logging.getLogger ('alawin_migration')


def main (destination):
    from openerp.modules.registry import RegistryManager

    registry = RegistryManager.get (destination, update_module=False)
    cr = registry.db.cursor ()

    Module = registry.get ('ir.module.module')

    update, add = Module.update_list (cr, 1)

    cr.commit ()

    module_ids = Module.search (cr, 1, [('name', '=', 'alawin_migration')])
    module = Module.browse (cr, 1, module_ids)[0]

    if module.state == 'uninstalled':
        _logger.info ('Cleaning database...')
        cleanup = open ('cleanup.sql')
        for line in cleanup.readlines ():
            line = line.strip ()
            if not line or line.startswith ('-'):
                continue

            cr.execute (line)

        cr.commit ()
        _logger.info ('Done.')

        module.button_install ()
        cr.commit ()

    _logger.info ('Reloading module.')

    module.write ({'state': 'to install'})

    cr.commit ()

    registry = RegistryManager.new (destination, update_module=True)

###    _logger.info ('Going to import data.')
###
###    modules = [
###        'sc_migration_account',
###        'sc_migration_account_journal',
###        'sc_migration_account_tax',
###        'sc_migration_region',
###        'sc_migration_country',
###        'sc_migration_analytic_account',
###        'sc_migration_fiscal_periods',
###        'sc_migration_account_model', # to review
###        'sc_migration_partner',
###        'sc_migration_account_move',
###        'sc_migration_payment_term',
###        'sc_migration_invoice',
###    ]
###
###    base = 'openerp.addons.alawin_migration.migrations'
###    for mname in modules:
###        mdl = importlib.import_module ('%s.%s' % (base, mname))
###        for cname, cls in inspect.getmembers (mdl, lambda x: inspect.isclass (x) and x.__module__ == mdl.__name__):
###            if not hasattr (cls, '_import_data'):
###                continue
###
###            migration = registry.get (cls._name)
###            cr = registry.db.cursor ()
###
###            try:
###                migration._import_data (cr)
###            except Exception, ex:
###                cr.rollback ()
###                raise
###            else:
###                cr.commit ()
###            finally:
###                cr.close ()


if __name__ == '__main__':
    if len (sys.argv) < 2:
        print "Usage: migrate.py [DESTIATION_DATABASE] [--debug]\n"
        sys.exit (1)

    from openerp.netsvc import init_logger

    init_logger ()

    if '--debug' in sys.argv:
        logging.basicConfig ()
        logging.getLogger('sqlalchemy.engine').setLevel (logging.INFO)

    destination = sys.argv[1]

    main (destination)
