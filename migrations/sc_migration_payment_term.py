# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import CondPagamTesta

from .base import Base
from .base import _strip


class sc_migration_payment_term (osv.Model, Base):

    _name = 'account.payment.term'
    _inherit = 'account.payment.term'

    _columns = {
        'alawin_codice': fields.text ('Alawin codice'),
    }

    def _import_data (self, cr):
        PaymentTerm = self.pool.get ('account.payment.term')
        PaymentTermLine = self.pool.get ('account.payment.term.line')

        print "Importing PaymentTerms..."

        if len (PaymentTerm.search (cr, 1, [])):
            return

        condizioni = self.alawin_session.query (CondPagamTesta).all ()

        print "%d Condizioni di Pagamento" % len (condizioni)

        for i, condizione in enumerate (condizioni):
            term_id = PaymentTerm.create (cr, 1, {
                'alawin_codice': _strip (condizione.codice),

                'name': _strip (condizione.descrizione),
                'note': _strip (condizione.descrizione),
            })

            for riga in condizione.righe:
                for j in range (riga.rate):
                    if j < riga.rate - 1:
                        month_day = {
                           'FM': -1,
                           'DF': 0,
                           'AV': 0,
                        }[riga.data_pref]

                        line_id = PaymentTermLine.create (cr, 1, {
                            'payment_id': term_id,

                            'days': riga.gg_partenza,
                            'days2': month_day,
                            'value': 'procent',
                            'value_amount': 1.0 / riga.rate,
                        })

                    else:
                        line_id = PaymentTermLine.create (cr, 1, {
                            'payment_id': term_id,

                            'days': riga.gg_partenza +  riga.gg_cadenza * j,
                            'days2': month_day,
                            'value': 'balance',
                            'value_amount': 0,
                        })

