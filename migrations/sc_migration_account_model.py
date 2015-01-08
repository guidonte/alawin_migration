# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import CausaliTesta
from ..db_alawin import CausaliRighe

from .base import Base
from .base import _strip


class sc_migration_account_model_line (osv.Model, Base):

    _name = 'account.model.line'
    _inherit = 'account.model.line'

    _columns = {
        'alawin_tipo': fields.text ('Alawin tipo'),
    }


class sc_migration_account_model (osv.Model, Base):

    _name = 'account.model'
    _inherit = 'account.model'

    _columns = {
        'alawin_codice': fields.text ('Alawin codice'),
        'alawin_tipo_registro': fields.text ('Alawin tipo_registro'),
    }

    def _import_data (self, cr):
        AccountModel = self.pool.get ('account.model')
        AccountModelLine = self.pool.get ('account.model.line')

        print "Importing Account Models..."

        if len (AccountModel.search (cr, 1, [])):
            return

        account_id_map = self.get_account_id_map ()
        journal_id_map = {
            'V': 1, # SAJ - Vendite
            'A': 2, # EXJ - Acquisti
            'G': 5, # MISC - Generale
            'C': 5, # MISC - Corrispettivi
        }

        causali = self.alawin_session.query (CausaliTesta).filter (
            CausaliTesta.codice_ditta=='1',
        ).all ()

        print "%d Causali" % len (causali)

        for i, causale in enumerate (causali):
            ### select distinct codice_causale from movimenti_testa where nr_mov in
            ### (select nr_mov from movimenti_righe where cod_iva is not null);
            # tipo_registro == 'V' (Vendite)
            # AFV - autofattura vendita
            # NCL - nota credito (cliente)
            # VES - vendita in sospensione
            # VEN - vendita
            # tipo_registro == 'A' (Acquisti')
            # ACQ - fattura di acquisto
            # AFA - autofattura acquisto
            # NFO - nota addebito (fornitore)

            if causale.codice == 'APE':
                journal_id = 6 # Opening Entries Journal - OPEJ
            elif causale.codice == 'NCL':
                journal_id = 3 # Sales Refund Journal - SCNJ
            elif causale.codice == 'NCO':
                journal_id = 4 # Purchase Refund Journal - ECNJ
            else:
                journal_id = journal_id_map[causale.tipo_registro]

            model_id = AccountModel.create (cr, 1, {
                'alawin_codice': causale.codice,
                'alawin_tipo_registro': causale.tipo_registro,

                'name': _strip (causale.codice),
                'legend': _strip (causale.descrizione),
                'company_id': 1,
                'journal_id': journal_id,
            })

            righe = self.alawin_session.query (CausaliRighe).filter (
                CausaliRighe.codice_ditta==causale.codice_ditta,
                CausaliRighe.codice_causale==causale.codice,
            ).all ()

            for riga in righe:
                line_id = AccountModelLine.create (cr, 1, {
                    'alawin_tipo': riga.tipo,

                    'model_id': model_id,
                    'name': _strip (causale.codice),
                    'sequence': riga.crt_no,
                    'account_id': account_id_map[riga.nr_corrente],
                })

