# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import MovimentiTesta

from .base import Base
from .base import _strip

from sqlalchemy.orm import joinedload

from collections import Counter
from decimal import Decimal
from decimal import ROUND_HALF_UP
import calendar
import re


def roundf (amount):
    if amount is None:
        return

    return Decimal.from_float (amount).quantize (Decimal('.01'), ROUND_HALF_UP)


class sc_migration_account_move_line (osv.Model, Base):

    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'alawin_nr_mov': fields.integer ('Alawin nr_mov'),
        'alawin_num': fields.integer ('Alawin num'),
    }


class sc_migration_account_move (osv.Model, Base):

    _name = 'account.move'
    _inherit = 'account.move'

    _columns = {
        'alawin_nr_mov': fields.integer ('Alawin nr_mov'),
        'alawin_num_registrazione': fields.integer ('Alawin num_registrazione'),
        'alawin_data_documento': fields.date ('Alawin data_documento'),
        'alawin_num_documento': fields.text ('Alawin num_documento'),
        'alawin_num_protocollo': fields.integer ('Alawin num_protocollo'),
        'alawin_id_doc': fields.integer ('Alawin id_doc'),
        'alawin_codice_causale': fields.text ('Alawin codice_causale'),
        'alawin_num_gio': fields.integer ('Alawin num_gio'),
        'alawin_attivita': fields.integer ('Alawin attivita'),

        'alawin_period_mismatch': fields.float ('Alawin period_mismatch'),
        'alawin_debit_mismatch': fields.float ('Alawin debit_mismatch'),
        'alawin_credit_mismatch': fields.float ('Alawin credit_mismatch'),
        'alawin_balance_mismatch': fields.float ('Alawin balance_mismatch'),
        'alawin_vat_mismatch': fields.float ('Alawin vat_mismatch'),
        'alawin_with_vat': fields.boolean ('Alawin with_vat'),
    }

    def _fix_moves (self, cr):
        AccountMove = self.pool.get ('account.move')

        account_moves = AccountMove.browse (cr, 1,
            AccountMove.search (cr, 1, [('to_check', '=', 'True')]))

        movimenti_map = dict ([(m.nr_mov, m) for m in self.alawin_session.query (MovimentiTesta).filter (
            MovimentiTesta.nr_mov.in_ ([a.alawin_nr_mov for a in account_moves]),
        ).options (
            joinedload ('righe'),
        ).all ()])

        i = 1
        for move in sorted (account_moves, key=lambda a: a.id):
            if abs (move.alawin_vat_mismatch) <= 0.015:
                for line in move.line_id:
                    if not line.account_id.code.startswith ('8.'):
                        continue

                    for riga in movimenti_map[move.alawin_nr_mov].righe:
                        if not riga.importo_iva:
                            continue

                        if line.account_id.code == '8.1':
                            if line.credit == riga.importo_iva:
                                continue

                            if abs (line.credit - riga.importo_iva) > 0.01:
                                continue

                            move.write ({'state': 'draft', 'to_check': False})
                            line.write ({'credit': riga.importo_iva})

                        elif line.account_id.code == '8.2':
                            if line.debit == riga.importo_iva:
                                continue

                            if abs (line.debit - riga.importo_iva) > 0.01:
                                continue

                            move.write ({'state': 'draft', 'to_check': False})
                            line.write ({'debit': riga.importo_iva})

            else:
                for line in move.line_id:
                    if not line.debit:
                        continue

                    for riga in movimenti_map[move.alawin_nr_mov].righe:
                        if line.debit != riga.importo_iva:
                            continue

                        if line.tax_code_id:
                            continue

                        move.write ({'state': 'draft', 'to_check': False})
                        line.unlink ()

                        i += 1
                        break

    def _import_data (self, cr):
        AccountMove = self.pool.get ('account.move')
        AccountMoveLine = self.pool.get ('account.move.line')

        print "Importing Journal Entries..."

        if len (AccountMove.search (cr, 1, [])):
            self._fix_moves (cr)
            return

        partner_map = self.get_partner_map (cr)
        account_id_map = self.get_account_id_map ()
        analytic_id_map = self.get_analytic_id_map ()
        iva_id_map = self.get_iva_id_map ()
        journal_map = {
             self.get_journal_id ('SAJ'): 'sale',
             self.get_journal_id ('SCNJ'): 'sale',

             self.get_journal_id ('SAJ74'): 'sale',
             self.get_journal_id ('SNJ74'): 'sale',

             self.get_journal_id ('SAAUJ'): 'sale',

             self.get_journal_id ('EXJ'): 'purchase',
             self.get_journal_id ('ECNJ'): 'purchase',

             self.get_journal_id ('EXJ74'): 'purchase',
             self.get_journal_id ('ENJ74'): 'purchase',

             self.get_journal_id ('EXAUJ'): 'purchase',
        }

        movimenti = self.get_chosen_moves ()

        print "%d Movimenti" % len (movimenti)

        iva_conto_vendite = self.iva_conto_vendite
        iva_conto_acquisti = self.iva_conto_acquisti

        # Causali con num_protocollo
        # VES VEN ACQ NCL AFA NFO AFV
        # APE CHI RIS EEA

        not_found_analytic_accounts = Counter ()

        for i, movimento in enumerate (movimenti):
            to_check = False
            narration = []

            special = True if movimento.codice_causale == 'APE' else False
            journal_id = self.find_journal (movimento)

            try:
                period_id = self.find_period (movimento.data_registrazione, special=special)
                period_mismatch = False
            except KeyError:
                # FIXME: change date instead instead of period
                period_id = self.find_period (movimento.data_registrazione, special=False)

                period_mismatch = True
                to_check = True
                narration.append ('Period key error: %s' % ((movimento.data_registrazione, special),))

            prefix = None
            if movimento.codice_causale in ['ACQ', 'AFA', 'NF0']:
                prefix = {1: 'EXJ', 2: 'EXJ74', 3: 'EXAUJ'}[movimento.attivita]
            elif movimento.codice_causale in ['VEN', 'VES', 'AFV', 'NCL']:
                prefix = {1: 'SAJ', 2: 'SAJ74', 3: 'SAAUJ'}[movimento.attivita]

            name = '/'

            year = int (movimento.data_registrazione.split ('-')[0])
            if prefix is not None:
                name = '%s/%d/%04d' % (prefix, year, movimento.num_protocollo)

            move_partner = partner_map.get (movimento.intestatario)

            move_id = AccountMove.create (cr, 1, {
                'alawin_nr_mov': movimento.nr_mov,
                'alawin_num_registrazione': movimento.num_registrazione,
                'alawin_data_documento': movimento.data_documento,
                'alawin_num_documento': movimento.num_documento,
                'alawin_num_protocollo': movimento.num_protocollo,
                'alawin_id_doc': movimento.id_doc,
                'alawin_codice_causale': movimento.codice_causale,
                'alawin_num_gio': movimento.num_gio,
                'alawin_attivita': movimento.attivita,

                'name': name,
                'ref': _strip (movimento.descrizione_mov),
                'state': 'draft',
                'date': movimento.data_registrazione,
                'company_id': 1,
                'journal_id': journal_id,
                'partner_id': move_partner.id if move_partner else None,
                'period_id': period_id,
            })

            debit_amount = credit_amount = 0
            righe_iva = []
            importi_iva = sorted ([r.importo_iva for r in movimento.righe if r.importo_iva])
            importo_iva = 0

            for riga in movimento.righe:
                partner_id = None
                #codice_fiscale = _strip (riga.conto.base.codice_fiscale)
                codice_fiscale = riga.conto.base.codice_fiscale
                if codice_fiscale:
                    partner_id = partner_map[codice_fiscale].id

                if re.match ('^6.[1|2|3].', riga.conto.base.codice):
                    account_id = account_id_map[riga.conto.base.parent.nr_corrente]
                    if not partner_id:
                        raise Exception ("Customer partner is missing")
                elif re.match ('^24.[1|2|3].', riga.conto.base.codice):
                    account_id = account_id_map[riga.conto.base.parent.nr_corrente]
                    if not partner_id:
                        raise Exception ("Supplier partner is missing")
                else:
                    account_id = account_id_map[riga.sottoconto]

                if riga.importo >= 0:
                    debit = riga.importo if riga.dare_avere == 'D' else 0
                    credit = riga.importo if riga.dare_avere == 'A' else 0
                else:
                    debit = -riga.importo if riga.dare_avere == 'A' else 0
                    credit = -riga.importo if riga.dare_avere == 'D' else 0

                debit_amount += roundf (debit)
                credit_amount += roundf (credit)

                # skip IVA lines. They are automatically generated based on
                # importo_iva and tax account data
                if importi_iva and account_id in [iva_conto_vendite.id, iva_conto_acquisti.id]:
                    righe_iva.append (riga)

                    if journal_id in [1, 4]:
                        importo_iva += riga.importo
                    else:
                        importo_iva -= riga.importo

                    continue

                iva_id = iva_id_map[(riga.cod_iva, journal_map[journal_id])] if riga.cod_iva else None

                # select nr_mov, num, importo, importo_ip, importo_iva
                # from movimenti_righe where importo_ip != 0 and importo_ip is not null and importo_ip != importo;

                analytic_account_id = None
                if riga.cod_centro_costo:
                    analytic_account_id = analytic_id_map.get (riga.cod_centro_costo)
                    if not analytic_account_id:
                        not_found_analytic_accounts[riga.cod_centro_costo] += 1

                line_id = AccountMoveLine.create (cr, 1, {
                    'alawin_nr_mov': riga.nr_mov,
                    'alawin_num': riga.num,

                    'move_id': move_id,
                    'account_id': account_id,
                    'partner_id': partner_id,
                    'name': movimento.descrizione_mov, # FIXME: 64 char ==> movimento.num_riferimento
                    'debit': debit,
                    'credit': credit,
                    'quantity': 1,
                    'tax_amount': roundf (riga.importo_iva),
                    'account_tax_id': iva_id,
                    'analytic_account_id': analytic_account_id,
                })

            move = AccountMove.browse (cr, 1, [move_id])[0]

            debit_mismatch = credit_mismatch = balance_mismatch = 0

            d_amount = sum ([roundf (l.debit) for l in move.line_id])
            if debit_amount != d_amount:
                to_check = True
                narration.append ('Debit mismatch: %s' % debit_amount)
                debit_mismatch = d_amount - debit_amount

            c_amount = sum ([roundf (l.credit) for l in move.line_id])
            if credit_amount != c_amount:
                to_check = True
                narration.append ('Credit mismatch: %s' % credit_amount)
                credit_mismatch = c_amount - credit_amount

            balance_mismatch = d_amount - c_amount
            if balance_mismatch:
                to_check = True
                narration.append ('Balance mismatch: %s' % balance_mismatch)

            vat_amounts = sorted ([l.tax_amount for l in move.line_id if l.tax_amount and not l.alawin_nr_mov])
            vat_amount = sum (vat_amounts)
            vat_mismatch = vat_amount - importo_iva
            if vat_mismatch and vat_mismatch > 0.001:
                to_check = True
                narration.append ('VAT mismatch: %s' % vat_mismatch)

            move.write ({
                'to_check': to_check,
                'narration': '\n'.join (narration),
                'alawin_period_mismatch': True if period_mismatch else False,
                'alawin_debit_mismatch': debit_mismatch,
                'alawin_credit_mismatch': credit_mismatch,
                'alawin_balance_mismatch': balance_mismatch,
                'alawin_vat_mismatch': vat_mismatch,
                'alawin_with_vat': True if righe_iva else False,
            })

            print "Movimento", i

        print "NOT FOUND ANALYTIC ACCOUNTS:", not_found_analytic_accounts

