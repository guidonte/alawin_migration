# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import PianoConti

from .base import Base
from .base import _strip


class sc_migration_account_journal (osv.Model, Base):

    _name = 'account.journal'
    _inherit = 'account.journal'

    def _get_analytic_journals (self, cr):
        AnalyticJournal = self.pool.get ('account.analytic.journal')

        journals = [
            {'name': 'Sales', 'code': 'SAL', 'type': 'sale'},
            {'name': 'Purchases', 'code': 'PUR', 'type': 'purchase'},
            {'name': 'General', 'code': 'GEN', 'type': 'general'},
            {'name': 'Cash and Bank', 'code': 'CASH', 'type': 'cash'},
            {'name': 'Opening', 'code': 'OPE', 'type': 'situation'},
        ]

        analytic_journal_map = {}
        for journal in journals:
            journal_id = AnalyticJournal.search (cr, 1, [
                ('type', '=', journal['type']),
            ])

            if journal_id:
                AnalyticJournal.browse (cr, 1, journal_id)[0].write (journal)
                journal_id = journal_id[0]
            else:
                journal_id = AnalyticJournal.create (cr, 1, journal)

            analytic_journal_map[journal['type']] = journal_id

        return analytic_journal_map

    def _import_data (self, cr):
        AccountJournal = self.pool.get ('account.journal')
        AnalyticJournal = self.pool.get ('account.analytic.journal')
        Sequence = self.pool.get ('ir.sequence')

        print "Setting up Journals..."
        if len (AccountJournal.search (cr, 1, [('type', '=', 'bank')])) > 1:
            return

        account_id_map = self.get_account_id_map ()
        analytic_journal_map = self._get_analytic_journals (cr)

        AccountJournal.unlink (cr, 1, AccountJournal.search (cr, 1, [('type', '=', 'bank')]))

        conti_banca = self.alawin_session.query (PianoConti).filter (
            PianoConti.codice_ditta=='1',
            PianoConti.sottoconto=='S',
            PianoConti.sotto_tipo=='B',
        ).all ()

        # add 'res_bank' and 'res_partner_bank' objects
        for i, conto_banca in enumerate (conti_banca):
            AccountJournal.create (cr, 1, {
                'code': 'BNK%d' % (i+2), # skip BNK1 - Cash
                'name': '%s - %s' % (_strip (conto_banca.codice), _strip (conto_banca.descrizione)),
                'type': 'bank',
                'analytic_journal_id': analytic_journal_map['cash'],
                'default_debit_account_id': account_id_map[conto_banca.nr_corrente],
                'default_credit_account_id': account_id_map[conto_banca.nr_corrente],
            })

        AccountJournal.create (cr, 1, {
            'code': 'SAJ74',
            'name': 'Sales 74/ter Journal',
            'type': 'sale',
        })

        AccountJournal.create (cr, 1, {
            'code': 'SNJ74',
            'name': 'Sales Refund 74/ter Journal',
            'type': 'sale_refund',
        })

        AccountJournal.create (cr, 1, {
            'code': 'SAAUJ',
            'name': 'Sales Auto Invoice Journal',
            'type': 'sale',
        })

        AccountJournal.create (cr, 1, {
            'code': 'EXJ74',
            'name': 'Purchase 74/ter Journal',
            'type': 'purchase',
        })

        AccountJournal.create (cr, 1, {
            'code': 'ENJ74',
            'name': 'Purchase Refund 74/ter Journal',
            'type': 'purchase_refund',
        })

        AccountJournal.create (cr, 1, {
            'code': 'EXAUJ',
            'name': 'Purchase Auto Invoice Journal',
            'type': 'purchase',
        })

        for journal in AccountJournal.browse (cr, 1, AccountJournal.search (cr, 1, [])):
            if journal.type in ['sale', 'sale_refund']:
                journal.write ({
                    'analytic_journal_id': analytic_journal_map['sale'],
                })
                if journal.code == 'SCNJ':
                    journal.write ({
                        'sequence_id': Sequence.search (cr, 1, [('name', '=', 'Sales Journal')])[0],
                    })
                elif journal.code == 'SNJ74':
                    journal.write ({
                        'sequence_id': Sequence.search (cr, 1, [('name', '=', 'Sales 74/ter Journal')])[0],
                    })
            elif journal.type in ['purchase', 'purchase_refund']:
                journal.write ({
                    'analytic_journal_id': analytic_journal_map['purchase'],
                })
                if journal.code == 'ECNJ':
                    journal.write ({
                        'sequence_id': Sequence.search (cr, 1, [('name', '=', 'Purchase Journal')])[0],
                    })
                elif journal.code == 'ENJ74':
                    journal.write ({
                        'sequence_id': Sequence.search (cr, 1, [('name', '=', 'Purchase 74/ter Journal')])[0],
                    })
            elif journal.type == 'cash':
                journal.write ({
                    'analytic_journal_id': analytic_journal_map['cash'],
                    'default_debit_account_id': self.conto_cassa.id,
                    'default_credit_account_id':  self.conto_cassa.id,
                })
            elif journal.type == 'general':
                journal.write ({
                    'analytic_journal_id': analytic_journal_map['general'],
                })
            elif journal.type == 'situation':
                journal.write ({
                    'analytic_journal_id': analytic_journal_map['situation'],
                    'centralisation': False,
                })

            journal.write ({
                'allow_date': True,
            })

