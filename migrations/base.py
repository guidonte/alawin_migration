# -*- coding: utf-8 -*-

from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import joinedload

from openerp.osv import osv

from ..db_alawin import AlawinBase
from ..db_alawin import ClientiFornitoriComuna

from ..db_sc import ScBase

from ..db_sc import ScPeriod
from ..db_sc import ScPartner
from ..db_sc import ScCountry
from ..db_sc import ScRegion
from ..db_sc import ScProvince
from ..db_sc import ScJournal
from ..db_sc import ScProduct
from ..db_sc import ScAnalyticAccount
from ..db_sc import ScAccount
from ..db_sc import ScAccountTax
from ..db_sc import ScAccountTaxCode
from ..db_sc import ScAccountModel
from ..db_sc import ScAccountModelLine
from ..db_sc import ScAccountMove
from ..db_sc import ScAccountMoveLine
from ..db_sc import ScAccountModel
from ..db_sc import ScAccountModelLine
from ..db_sc import ScPaymentTerm

import calendar
import datetime
import json

import sys


class Base (osv.AbstractModel):

    _name = 'sc.migration.base'

    def __init__ (self, *args, **kwargs):
        super (Base, self).__init__ (*args, **kwargs)

        self._alawin_db = 'ala_test_06_10_2014' #  FIXME
        self._alawin_engine = None
        self._alawin_metadata = None
        self._AlawinSession = None
        self._alawin_session = None

        self._openerp_db = 'openerp' #  FIXME sys.argv[1]
        self._openerp_engine = None
        self._openerp_metadata = None
        self._ScSession = None
        self._openerp_session = None

        self.start_date = '2014-01-01'
        self.end_date = '2014-12-31'

    @property
    def alawin_engine (self):
        if not self._alawin_engine:
            self._alawin_engine = create_engine ('postgresql://localhost/%s' % self._alawin_db)#, echo=True)

        return self._alawin_engine

    @property
    def alawin_metadata (self):
        if not self._alawin_metadata:
            self._alawin_metadata = MetaData (self.alawin_engine)

        return self._alawin_metadata

    @property
    def AlawinSession (self):
        if not self._AlawinSession:
            self._AlawinSession = sessionmaker (bind=self.alawin_engine)

        return self._AlawinSession

    @property
    def alawin_session (self):
        if not self._alawin_session:
            Session = sessionmaker (bind=self.alawin_engine)
            self._alawin_session = Session ()

        return self._alawin_session

    @property
    def openerp_engine (self):
        if not self._openerp_engine:
            self._openerp_engine = create_engine ('postgresql://localhost/%s' % self._openerp_db)

        return self._openerp_engine

    @property
    def openerp_metadata (self):
        if not self._openerp_metadata:
            self._openerp_metadata = MetaData (self.openerp_engine)

        return self._openerp_metadata

    @property
    def ScSession (self):
        if not self._ScSession:
            self._ScSession = sessionmaker (bind=self.openerp_engine)

        return self._ScSession

    @property
    def openerp_session (self):
        if not self._openerp_session:
            Session = sessionmaker (bind=self.openerp_engine)
            self._openerp_session = Session ()

        return self._openerp_session

    def _import_data (self, cr):
        pass

    def _auto_init (self, cr, context=None):
        ret = super (Base, self)._auto_init (cr, context=None)

        if '--import-data' in sys.argv:
            AlawinBase.prepare (self.alawin_engine)
            ScBase.prepare (self.openerp_engine)

            self._import_data (cr)

        return ret

    def get_chosen_moves (self):
        from ..db_alawin import MovimentiTesta

        movimenti = self.alawin_session.query (MovimentiTesta).filter (
            MovimentiTesta.codice_ditta=='1',
            MovimentiTesta.data_registrazione>=self.start_date,
            MovimentiTesta.data_registrazione<=self.end_date,
        ).options (
            joinedload ('righe'),
            joinedload ('righe.conto'),
            joinedload ('righe.conto.base'),
        ).all ()

        return movimenti

    def get_chosen_invoices (self):
        from ..db_alawin import Documento

        documenti = self.alawin_session.query (Documento).filter (
            Documento.codice_ditta=='1',
            Documento.data_registrazione>=self.start_date,
            Documento.data_registrazione<=self.end_date,
        ).options (
            joinedload ('righe'),
            joinedload ('righe.articolo'),
            joinedload ('cliente_fornitore'),
            joinedload ('cliente_fornitore.sottoconto'),
            joinedload ('cliente_fornitore.sottoconto.base'),
            joinedload ('movimento_testa'),
        ).all ()

        return documenti

    def get_province_map (self):
        sc_session = self.ScSession ()

        province_map = {}
        for province in sc_session.query (ScProvince).all ():
            province_map[province.code] = province.id

        return province_map

    def get_region_id_map (self):
        sc_session = self.ScSession ()

        region_map = {}
        for region in sc_session.query (ScRegion).all ():
            if region.alawin_id:
                region_map[region.alawin_id] = region.id

        return region_map

    def get_country_id_map (self):
        sc_session = self.ScSession ()

        country_map = {}
        for country in sc_session.query (ScCountry).all ():
            if country.alawin_id:
                country_map[country.alawin_id] = country.id

        return country_map

    def get_country_code_map (self):
        sc_session = self.ScSession ()

        country_map = {}
        for country in sc_session.query (ScCountry).all ():
            if country.alawin_id:
                country_map[country.alawin_id] = country.code

        return country_map

    def get_partner_map (self, cr):
        Partner = self.pool.get ('res.partner')

        partner_map = {}
        for partner in Partner.browse (cr, 1, Partner.search (cr, 1, [])):
            if partner.alawin_codice_fiscale:
                partner_map[partner.alawin_codice_fiscale] = partner

        return partner_map

    def get_payment_term_id_map (self):
        sc_session = self.ScSession ()

        payment_term_map = {}
        for payment_term in sc_session.query (ScPaymentTerm).all ():
            if payment_term.alawin_codice:
                payment_term_map[payment_term.alawin_codice] = payment_term.id

        return payment_term_map

    def get_existing_analytic_accounts (self):
        sc_session = self.ScSession ()

        analytic_map = {}
        for analytic in sc_session.query (ScAnalyticAccount).all ():
            if not analytic.alawin_id_costo:
                analytic_map[_strip (analytic.name)] = analytic.id

        return analytic_map

    def get_analytic_id_map (self):
        sc_session = self.ScSession ()

        analytic_map = {}
        for analytic in sc_session.query (ScAnalyticAccount).all ():
            if analytic.alawin_id_costo:
                analytic_map[analytic.alawin_id_costo] = analytic.id

        return analytic_map

    def get_account_id_map (self):
        sc_session = self.ScSession ()

        account_map = {}
        for account in sc_session.query (ScAccount).all ():
            if account.alawin_nr_corrente:
                account_map[account.alawin_nr_corrente] = account.id

        return account_map

    @property
    def iva_conto_vendite (self):
        return self.openerp_session.query (ScAccount).filter_by (code='8.1').one ()

    @property
    def iva_conto_acquisti (self):
        return self.openerp_session.query (ScAccount).filter_by (code='8.2').one ()

    @property
    def conto_bilancio_apertura (self):
        return self.openerp_session.query (ScAccount).filter_by (code='22.1').one ()

    @property
    def conto_bilancio_chiusura (self):
        return self.openerp_session.query (ScAccount).filter_by (code='22.2').one ()

    @property
    def conto_cassa (self):
        return self.openerp_session.query (ScAccount).filter_by (code='10.1.1').one ()

    @property
    def conto_ricavi_default (self):
        return self.openerp_session.query (ScAccount).filter_by (code='51.100').one ()

    @property
    def conto_acquisti_default (self):
        return self.openerp_session.query (ScAccount).filter_by (code='61.100').one ()

    def get_conto (self, code):
        return self.openerp_session.query (ScAccount).filter_by (code=code).one ()

    def get_conto_cliente (self, codice_fiscale):
        return self.get_conto_from_codice_fiscale (codice_fiscale, 'CLIENTE')

    def get_conto_fornitore (self, codice_fiscale):
        return self.get_conto_from_codice_fiscale (codice_fiscale, 'FORNITORE')

    def get_conto_from_codice_fiscale (self, codice_fiscale, category):
        if not hasattr (self.__class__, '_c_map'):
            alawin_session = self.AlawinSession ()

            c_map = {
                'CLIENTE': {},
                'FORNITORE': {},
            }

            for cliente in alawin_session.query (ClientiFornitoriComuna).options (
                joinedload ('conti'),
                joinedload ('conti.parent'),
            ).filter (
                ClientiFornitoriComuna.codice_ditta=='1',
            ).all ():
                for conto in cliente.conti:
                    if _strip (conto.codice_ditta) != '1':
                        continue

                    if conto.codice.startswith ('6'):
                        c_map['CLIENTE'].setdefault (cliente.codice_fiscale, []).append (conto)
                    elif conto.codice.startswith ('24'):
                        c_map['FORNITORE'].setdefault (cliente.codice_fiscale, []).append (conto)

            self.__class__._c_map = c_map

        conti = self._c_map[category].get (codice_fiscale)
        if not conti:
            return

        return conti[0].parent

    def get_iva_id_map (self):
        sc_session = self.ScSession ()

        iva_map = {}
        for iva in sc_session.query (ScAccountTax).all ():
            if iva.alawin_codice_iva:
                iva_map[(iva.alawin_codice_iva, iva.type_tax_use)] = iva.id

        return iva_map

    def get_tax_code_map (self):
        sc_session = self.ScSession ()

        code_map = {}
        for code in sc_session.query (ScAccountTaxCode).all ():
            code_map[code.code] = code.id

        return code_map

    def get_move_map (self):
        sc_session = self.ScSession ()

        move_map = {}
        for move in sc_session.query (ScAccountMove).options (joinedload ('lines')).all ():
            if move.alawin_nr_mov:
                move_map[move.alawin_nr_mov] = move

        return move_map

    def get_product_id_map (self):
        sc_session = self.ScSession ()

        product_map = {}
        for account in sc_session.query (ScAnalyticAccount).all ():
            if account.alawin_cod_art:
                product_map[account.alawin_cod_art] = account.id

        return product_map

    def get_product_map (self):
        sc_session = self.ScSession ()

        product_map = {}
        for product in sc_session.query (ScProduct).all ():
            if product.alawin_cod_art:
                product_map[product.alawin_cod_art] = product

        return product_map

    def get_periods (self):
        sc_session = self.ScSession ()

        if not hasattr (self.__class__, '_periods'):
            self.__class__._periods = sc_session.query (ScPeriod).all ()

        return self.__class__._periods

    def get_date_map (self):
        if not hasattr (self.__class__, '_date_map'):
            date_map = {}

            for period in self.get_periods ():
                start = datetime.date (*[int (d) for d in period.date_start.split ('-')])
                stop = datetime.date (*[int (d) for d in period.date_stop.split ('-')])

                for delta in range (calendar.monthrange (start.year, start.month)[1]):
                    day = start + datetime.timedelta (days=delta)
                    if day > stop:
                        break

                    if day < start:
                        continue

                    date_map[(day, period.special)] = period.id

            self.__class__._date_map = date_map

        return self.__class__._date_map

    def find_period (self, date, special=False):
        date_map = self.get_date_map ()

        if isinstance (date, basestring):
            date = datetime.date (*[int (d) for d in date.split ('-')])
        elif isinstance (date, datetime):
            date = date.date ()

        return date_map[(date, special)]

    def get_journal_id (self, code):
        if not hasattr (self.__class__, '_journal_map'):
            sc_session = self.ScSession ()

            journal_map = {}
            for journal in sc_session.query (ScJournal).all ():
                journal_map[journal.code] = journal.id

            self.__class__._journal_map = journal_map

        return self._journal_map[code]

    def find_journal (self, movimento):
        code = movimento.codice_causale
        activity = movimento.attivita

        if not hasattr (self.__class__, '_model_map'):
            sc_session = self.ScSession ()

            model_map = {}
            for model in sc_session.query (ScAccountModel).all ():
                model_map[(model.name, None)] = model.journal_id

            for journal in sc_session.query (ScJournal).all ():
                model_map[('INC', journal.default_debit_account_id)] = journal.id
                model_map[('TES', journal.default_debit_account_id)] = journal.id
                model_map[('AFT', journal.default_debit_account_id)] = journal.id

                model_map[('SFO', journal.default_credit_account_id)] = journal.id
                model_map[('AFO', journal.default_credit_account_id)] = journal.id
                model_map[('ADD', journal.default_credit_account_id)] = journal.id
                model_map[('SBA', journal.default_credit_account_id)] = journal.id
                model_map[('CSB', journal.default_credit_account_id)] = journal.id
                model_map[('PRM', journal.default_credit_account_id)] = journal.id
                model_map[('MUT', journal.default_credit_account_id)] = journal.id
                model_map[('RSP', journal.default_credit_account_id)] = journal.id
                model_map[('ECM', journal.default_credit_account_id)] = journal.id
                model_map[('PRA', journal.default_credit_account_id)] = journal.id
                model_map[('CCS', journal.default_credit_account_id)] = journal.id
                model_map[('PCH', journal.default_credit_account_id)] = journal.id

            self.__class__._model_map = model_map
            self.__class__._account_id_map = self.get_account_id_map ()

        if code in ['INC', 'AFT', 'TES']:
            for riga in movimento.righe:
                if riga.dare_avere == 'D' and riga.importo:
                    account_id = self._account_id_map.get (riga.sottoconto)
                    journal_id = self._model_map.get ((code, account_id))

                    if account_id and journal_id: return journal_id

            return self.get_journal_id ('MISC')

        if code in ['AFO', 'SFO', 'ADD', 'SBA', 'CSB', 'PRM', 'MUT', 'RSP',
                    'ECM', 'PRA', 'CCS', 'PCH']:
            for riga in movimento.righe:
                if riga.dare_avere == 'A' and riga.importo:
                    account_id = self._account_id_map.get (riga.sottoconto)
                    journal_id = self._model_map.get ((code, account_id))

                    if account_id and journal_id: return journal_id

            return self.get_journal_id ('MISC')

        if activity == 2:
            if code in ['ACQ', 'AFA']: # Fatture di acquisto, autofatture
                return self.get_journal_id ('EXJ74')
            elif code == 'VEN':
                return self.get_journal_id ('SAJ74')

        if activity == 3:
            if code in ['ACQ', 'AFA']: # Fatture di acquisto, autofatture
                return self.get_journal_id ('EXAUJ')
            elif code == 'VEN':
                return self.get_journal_id ('SAAUJ')

        return self._model_map.get ((code, None)) or self.get_journal_id ('MISC')

    def update_settings (self, cr, props={}):
        settings_obj = self.pool.get ('account.config.settings')
        settings_ids = settings_obj.search (cr, 1, [])
        if not settings_ids:
            config = {
                "default_sale_tax" : 204,
                "default_purchase_tax" : 205,

                "purchase_journal_id" : self.get_journal_id ('EXJ'),
                "purchase_refund_journal_id" : self.get_journal_id ('ECNJ'),
                "purchase_tax" : None,
                "purchase_tax_rate" : 22,
                "sale_journal_id" : self.get_journal_id ('SAJ'),
                "sale_refund_journal_id" : self.get_journal_id ('SCNJ'),
                "sale_tax" : None,
                "sale_tax_rate" : 22,

                "chart_template_id" : None,
                "code_digits" : 0,
                "company_id" : 1,
                "complete_tax_set" : False,
                "date_start" : "2014-01-01",
                "date_stop" : "2014-12-31",
                "decimal_precision" : 2,
                "group_analytic_account_for_sales" : False,
                "group_analytic_accounting" : True,
                "group_check_supplier_invoice_total" : False,
                "group_multi_currency" : False,
                "group_proforma_invoices" : False,
                "has_chart_of_accounts" : True,
                "has_default_company" : True,
                "has_fiscal_year" : True,
                "module_account_accountant" : True,
                "module_account_asset" : True,
                "module_account_budget" : True,
                "module_account_check_writing" : False,
                "module_account_followup" : False,
                "module_account_payment" : False,
                "module_account_voucher" : True,
                "module_sale_analytic_plans" : False,
                "period" : "month",
            }

            config.update (props)

            settings_ids = [settings_obj.create (cr, 1, config)]

        settings = settings_obj.browse (cr, 1, settings_ids)[0]

        settings.write (props)

        settings.set_default_taxes ()

def _strip (txt):
    return txt.strip () if txt is not None else txt

def _rstrip (txt):
    return txt.rstrip () if txt is not None else txt

