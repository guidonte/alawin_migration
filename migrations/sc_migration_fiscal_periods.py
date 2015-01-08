# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import MovimentiTesta

from .base import Base
from .base import _strip

import calendar
import datetime


YEARS = []


class sc_migration_account_fiscalyear (osv.Model, Base):

    _name = 'account.fiscalyear'
    _inherit = 'account.fiscalyear'

    def _import_data (self, cr):
        FiscalYear = self.pool.get ('account.fiscalyear')

        print "Configuring Fiscal Years..."

        for year in YEARS:
            if len (FiscalYear.search (cr, 1, [('code', '=', str (year))])):
                continue

            year_id = FiscalYear.create (cr, 1, {
                'code': str (year),
                'name': str (year),
                'state': 'draft',
                'date_start': datetime.date (year, 1, 1),
                'date_stop': datetime.date (year, 12, 31),
                'prorata': 0,
            })

        FiscalYear.write (cr, 1, FiscalYear.search (cr, 1, [('name', '=', '2014')]), {
            'code': '2014',
            'prorata': 17.0,
        })


class sc_migration_account_period (osv.Model, Base):

    _name = 'account.period'
    _inherit = 'account.period'

    def _import_data (self, cr):
        FiscalYear = self.pool.get ('account.fiscalyear')
        Period = self.pool.get ('account.period')

        print "Configuring Periods..."

        for year in YEARS:
            year_id = FiscalYear.search (cr, 1, [('code', '=', str (year))])[0]
            if len (Period.search (cr, 1, [('fiscalyear_id', '=', year_id)])):
                continue

            period_id = Period.create (cr, 1, {
                'code': '%02d/%d' % (0, year),
                'name': 'Opening Period %d' % year,
                'state': 'draft',
                'date_start': datetime.date (year, 1, 1),
                'date_stop': datetime.date (year, 1, 1),
                'fiscalyear_id': year_id,
                'special': True,
            })

            for month in range (1, 13):
                period_id = Period.create (cr, 1, {
                    'code': '%02d/%d' % (month, year),
                    'name': '%02d/%d' % (month, year),
                    'state': 'draft',
                    'date_start': datetime.date (year, month, 1),
                    'date_stop': datetime.date (year, month, calendar.monthrange (year, month)[1]),
                    'fiscalyear_id': year_id,
                    'special': False,
                })

