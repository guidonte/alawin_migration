# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from sqlalchemy.orm import joinedload

from ..db_alawin import Documento

from .base import Base
from .base import _strip

from collections import Counter
import datetime


class sc_migration_invoice_line (osv.Model, Base):

    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'alawin_num_documento': fields.integer ('Alawin num_documento'),
        'alawin_codce_ex': fields.integer ('Alawin codce_ex'),
    }


class sc_migration_invoice (osv.Model, Base):

    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'alawin_num_documento': fields.integer ('Alawin num_documento'),
        'alawin_data_registrazione': fields.date ('Alawin data_registrazione'),
        'alawin_amount_total_mismatch': fields.float ('Alawin amount_total_mismatch'),
        'alawin_amount_untaxed_mismatch': fields.float ('Alawin amount_untaxed_mismatch'),
        'alawin_amount_tax_mismatch': fields.float ('Alawin amount_tax_mismatch'),
        'alawin_attivita': fields.integer ('Alawin attivita'),
    }

    def _import_data (self, cr):
        Invoice = self.pool.get ('account.invoice')
        InvoiceLine = self.pool.get ('account.invoice.line')
        AccountMove = self.pool.get ('account.move')
        AccountMoveLine = self.pool.get ('account.move.line')
        AccountJournal = self.pool.get ('account.journal')

        print "Importing Invoices..."

        if len (Invoice.search (cr, 1, [])):
            return

        partner_map = self.get_partner_map (cr)
        account_id_map = self.get_account_id_map ()
        iva_id_map = self.get_iva_id_map ()
        move_map = self.get_move_map ()
        product_id_map = self.get_product_id_map ()
        product_map = self.get_product_map ()
        analytic_id_map = self.get_analytic_id_map ()
        payment_term_id_map = self.get_payment_term_id_map ()

        last_invoice_num = 0

        documenti = self.alawin_session.query (Documento).filter (
            Documento.codice_ditta=='1',
            Documento.data>=self.start_date,
            Documento.data<=self.end_date,
        ).options (
            joinedload ('righe'),
            joinedload ('righe.articolo'),
            joinedload ('cliente_fornitore'),
            joinedload ('cliente_fornitore.sottoconto'),
            joinedload ('cliente_fornitore.sottoconto.base'),
            joinedload ('movimento_testa'),
        ).all ()

        print "%d Documenti" % len (documenti)

        not_found_products = Counter ()
        for i, documento in enumerate (documenti):
            amount_total_mismatch = 0
            amount_untaxed_mismatch = 0
            amount_tax_mismatch = 0
            comment = []

            codice_fiscale = documento.cliente_fornitore.sottoconto.base.codice_fiscale
            partner = partner_map[codice_fiscale]
            account_id = partner.property_account_receivable.id
            #account_id = account_id_map[documento.interstatario]
            move = move_map[documento.movimento_testa.nr_mov] if documento.movimento_testa else None
            payment_term = payment_term_id_map.get (_strip (documento.codice_cond_pagamento))

            dtype = 'out_refund' if _strip (documento.serie) == 'NCL' else 'out_invoice'

            date_invoice = documento.data
            year = int (documento.data.split ('-')[0]) if documento.data else None
            state = 'open' if move else 'draft'

            num = None
            prefix = {1: 'SAJ', 2: 'SAJ74', 3: 'SAAUJ'}[documento.attivita]
            journal_id = self.get_journal_id (prefix)
            if state == 'open':
                num = documento.num
                if num > last_invoice_num and year == datetime.date.today ().year:
                    last_invoice_num = num

            number = '%s/%d/%04d' % (prefix, year, num) if num else None

            if move and number:
                AccountMove.write (cr, 1, [move.id], {
                    'name': number,
                    'state': 'posted',
                })

                journal_id = move.journal_id

            invoice_id = Invoice.create (cr, 1, {
                'alawin_num_documento': documento.num_documento,
                'alawin_data_registrazione': documento.data_registrazione,
                'alawin_attivita': documento.attivita,

                'type': dtype,
                'state': state,
                'journal_id': journal_id,
                'internal_number': '%d' % documento.num,
                'date_invoice': date_invoice,
                'period_id': self.find_period (documento.data, special=False),
                'partner_id': partner.id,
                'account_id': account_id,
                'move_id': move.id if move else None,
                'sent': True if documento.stampato == 'S' else False,
                'payment_term': payment_term,
            })

            for riga in documento.righe:
                if not riga.quantita or not riga.prezzo:
                    continue

                line_account_id = None
                if riga.contropartita:
                    line_account_id = account_id_map[riga.contropartita]

                if not line_account_id:
                    if riga.articolo and riga.articolo.sottoc_vendite:
                        line_account_id = account_id_map[riga.articolo.sottoc_vendite]

                if not line_account_id:
                    line_account_id = self.conto_ricavi_default.id

                iva_id = iva_id_map[(riga.cod_iva, 'sale')] if riga.cod_iva else None

                name = _strip (riga.note)

                account_analytic_id = product_id = None
                if riga.prezzo:
                    if riga.codice_centro_costo:
                        account_analytic_id = analytic_id_map[riga.codice_centro_costo]
                    elif riga.codce_ex:
                        product = product_map.get (riga.codce_ex)
                        if product:
                             product_id = product.id
                             if name:
                                 name = product.name_template + '. ' + name
                             else:
                                 name = product.name_template
                        account_analytic_id = product_id_map.get (riga.codce_ex)
                        if not account_analytic_id:
                            not_found_products[riga.codce_ex] += 1

                line_id = InvoiceLine.create (cr, 1, {
                    'alawin_num_documento': riga.num_documento,
                    'alawin_codce_ex': riga.codce_ex,

                    'invoice_id': invoice_id,
                    'name': name,
                    'quantity': riga.quantita,
                    'price_unit': riga.prezzo,
                    'sequence': riga.num_riga,
                    'account_id': line_account_id,
                    'invoice_line_tax_id': [(4, iva_id)] if iva_id else None,
                    'account_analytic_id': account_analytic_id,
                    'product_id': product_id,
                })

            Invoice.button_reset_taxes (cr, 1, [invoice_id])

            invoice = Invoice.browse (cr, 1, [invoice_id])[0]

            if move:
                for i_line in invoice.invoice_line:
                    for m_line in move.lines:
                        if m_line.account_id != i_line.account_id.id:
                            continue

                        if not m_line.credit or (m_line.credit != i_line.price_unit):
                            continue

                        AccountMoveLine.write (cr, 1, [m_line.id], {
                            'analytic_account_id': i_line.account_analytic_id.id,
                        })

            comment = []

            amount_total_mismatch = invoice.amount_total - documento.totale
            if amount_total_mismatch and amount_total_mismatch >= 0.01:
                comment.append ('Totale: %s' % documento.totale)
                comment.append ('Totale mismatch: %s' % amount_total_mismatch)

            amount_untaxed_mismatch = invoice.amount_untaxed - documento.total_merce
            if amount_untaxed_mismatch and amount_untaxed_mismatch >= 0.01:
                comment.append ('Imponibile: %s' % documento.total_merce)

            importo_iva = documento.totale - documento.total_merce
            amount_tax_mismatch = invoice.amount_tax - importo_iva
            if amount_tax_mismatch and amount_tax_mismatch >= 0.01:
                comment.append ('Importo IVA: %s' % importo_iva)
                comment.append ('IVA mismatch: %s' % amount_tax_mismatch)

            invoice.write ({
                'alawin_amount_total_mismatch': amount_total_mismatch,
                'alawin_amount_untaxed_mismatch': amount_untaxed_mismatch,
                'alawin_amount_tax_mismatch': amount_tax_mismatch,
                'comment': '\n'.join (comment) or None,
            })

            print "Documento", i

        print "NOT FOUND PRODUCTS:", not_found_products

        if last_invoice_num:
            journal = AccountJournal.browse (cr, 1,
                AccountJournal.search (cr, 1, [('code', '=', 'SAJ')]))[0]

            journal.sequence_id.write ({
                'number_next': int (last_invoice_num + 1),
            })

