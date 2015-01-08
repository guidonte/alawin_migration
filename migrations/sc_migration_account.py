# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import PianoConti

from .base import Base
from .base import _strip


class sc_migration_account (osv.Model, Base):

    _name = 'account.account'
    _inherit = 'account.account'

    _columns = {
        'alawin_nr_corrente': fields.integer ('Alawin nr_corrente'),
        'alawin_codice_fiscale': fields.text ('Alawin codice_fiscale'),
        'alawin_tipo': fields.text ('Alawin tipo'),
        'alawin_sotto_tipo': fields.text ('Alawin sotto_tipo'),
        'alawin_tipo_da': fields.text ('Alawin tipo_da'),
    }

    alawin_tipo_map = {
        'P': 'Patrimoniale',
        'E': 'Economico',
        'M': 'Magazzino', # usato solo per un conto base di Magazzino
        'O': 'Ordine', # non usato
    }

    alawin_sotto_tipo_map = {
        'B': 'Banca',
        'A': 'Cassa',
        'C': 'Clienti',
        'F': 'Fornitori',
        'H': 'Bilancio',
        'S': 'Cespite',
        'D': 'Fondo',
        'R': 'Rateo',
        'I': 'Iva',
        'N': 'Nessuno',
        'E': 'Economico', # per tutti i conti di tipo "E"
        'M': 'Magazzino', # per tutti i conti di tipo "M"
        'O': 'Ordine', # per tutti i conti di tipo "O"
    }

    def _get_account_type_map (self, cr):
        if not hasattr (self, '_account_type_map'):
            AccountType = self.pool.get ('account.account.type')

            self._account_type_map = {}

            account_types = AccountType.browse (cr, 1, AccountType.search (cr, 1, []))
            for account_type in account_types:
                self._account_type_map[account_type.name] = account_type.id

        return self._account_type_map

    def _get_account_type (self, conto, account_type_map):
        tipo = _strip (conto.tipo)
        tipo_da = _strip (conto.tipo_da)
        sottotipo = _strip (conto.sotto_tipo)
        sottoconto = False if conto.sottoconto == 'N' else True
        livello = conto.livello
        codice = _strip (conto.codice)
        descrizione = _strip (conto.descrizione)

        l = livello
        while l > 1:
            tipo_da = _strip (conto.parent.tipo_da)
            if tipo_da:
                break

            l -= 1

        if tipo == 'P':
            if not sottoconto and (not sottotipo in ['C', 'F'] or livello == 1):
                if tipo_da == 'A':
                    return account_type_map['Liability View']

                if tipo_da == 'D':
                    return account_type_map['Asset View']

                # only for conto 22. CONTI DI CHIUSURA APERTURA
                return account_type_map['Root/View']

            if sottotipo == 'C': # code.startswith ('6'):
                return account_type_map['Receivable']

            if sottotipo == 'F': # code.startswith ('24'):
                return account_type_map['Payable']

            if sottotipo == 'B':
                return account_type_map['Bank']

            if sottotipo == 'A':
                return account_type_map['Cash']

            if tipo_da == 'A':
                return account_type_map['Liability']

            if tipo_da == 'D':
                return account_type_map['Asset']

            # only for sottoconti of 22. CONTI DI CHIUSURA APERTURA
            return account_type_map['Root/View']

        if tipo == 'E':
            if sottotipo and sottotipo != 'E':
                 raise ValueError ("Wrong sottotipo for tipo E: '%s'" % sottotipo)

            if not sottoconto:
                if tipo_da == 'A':
                    return account_type_map['Income View']

                if tipo_da == 'D':
                    return account_type_map['Expense View']

                # only for conto 65. AMMORTAMENTI
                return account_type_map['Root/View']

            if tipo_da == 'A':
                return account_type_map['Income']

            if tipo_da == 'D':
                return account_type_map['Expense']

            # only for sottoconti of 65. AMMORTAMENTI
            return account_type_map['Root/View']

        raise ValueError ("Wrong tipo, sottotipo, tipo, sottoconto")

    def _import_data (self, cr):
        print "Importing Accounts..."

        Account = self.pool.get ('account.account')
        AccountType = self.pool.get ('account.account.type')

        if not len (Account.search (cr, 1, [])):
            raise Exception ("Base account is missing.")

        if len (Account.search (cr, 1, [])) > 1:
            return

        account_type_map = self._get_account_type_map (cr)

        conti = self.alawin_session.query (PianoConti).filter (
            PianoConti.codice_ditta=='1',
            PianoConti.nr_corrente_par!=-1,
            PianoConti.tipo!='M', # MILANO
            PianoConti.codice.notlike ('5 %'), # MAGAZZINO
            PianoConti.codice.notlike ('5.1 %'), # MAGAZZINO
            PianoConti.tipo!='O',

            PianoConti.codice.notlike ('30%'), # CONTI TRANSITO PATRIMONIALI
            PianoConti.codice.notlike ('31%'), # APERTURA - CHIUSURA PROVVISORIA
            PianoConti.codice.notlike ('70%'), # SVALUTAZIONI
            PianoConti.codice.notlike ('80%'), # P.P.

            PianoConti.codice.notlike ('6.1.%'),
            PianoConti.codice.notlike ('6.2.%'),
            PianoConti.codice.notlike ('6.3.%'),
            PianoConti.codice.notlike ('24.1.%'),
            PianoConti.codice.notlike ('24.2.%'),
            PianoConti.codice.notlike ('24.3.%'),
        ).order_by (PianoConti.livello).all ()

        print "%d Conti" % len (conti)

        conto_clienti_italia = conto_fornitori_italia = None
        conto_ricavi = conto_costi = None

        stato_patrimoniale_id = Account.create (cr, 1, {
            'code': 'P',
            'name': 'STATO PATRIMONIALE',
            'parent_id': 1,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        attivo_id = Account.create (cr, 1, {
            'code': 'PA',
            'name': 'ATTIVO',
            'parent_id': stato_patrimoniale_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        passivo_id = Account.create (cr, 1, {
            'code': 'PP',
            'name': 'PASSIVO',
            'parent_id': stato_patrimoniale_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        conto_economico_id = Account.create (cr, 1, {
            'code': 'E',
            'name': 'CONTO ECONOMICO',
            'parent_id': 1,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        costi_id = Account.create (cr, 1, {
            'code': 'EC',
            'name': 'COSTI',
            'parent_id': conto_economico_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        ricavi_id = Account.create (cr, 1, {
            'code': 'ER',
            'name': 'RICAVI',
            'parent_id': conto_economico_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        finanziari_id = Account.create (cr, 1, {
            'code': 'POF',
            'name': 'PROVENTI E ONERI FINANAZIARI',
            'parent_id': conto_economico_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        straordinari_id = Account.create (cr, 1, {
            'code': 'POS',
            'name': 'PROVENTI E ONERI STRAORDINARI',
            'parent_id': conto_economico_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        imposte_id = Account.create (cr, 1, {
            'code': 'IE',
            'name': "IMPOSTE DELL'ESERCIZIO",
            'parent_id': conto_economico_id,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        risultato_id = Account.create (cr, 1, {
            'code': 'R',
            'name': 'RISULTATO',
            'parent_id': None,
            'type': 'view',
            'user_type': account_type_map['Root/View'],
            'currency_mode': 'current',
            'reconcile': False,
            'company_id': 1,
        })

        account_map = {}
        for i, conto in enumerate (conti):
            code = _strip (conto.codice)

            user_type_id = self._get_account_type (conto, account_type_map)

            if conto.sottoconto == 'N':
                account_type = 'view'
            elif user_type_id in [account_type_map[c] for c in ['Cash', 'Bank', 'Check']]:
                account_type = 'liquidity'
            else:
                account_type = 'other'

            reconcile = False

            if code.startswith ('6.'):
                account_type = 'receivable'
                reconcile = True
            elif code.startswith ('24.'):
                account_type = 'payable'
                reconcile = True

            if conto.nr_corrente_par:
                if code == '24.4': # spurious account S.PASSALACQUA S.P.A
                    continue
                else:
                    parent_id = account_map[conto.nr_corrente_par]
            else:
                # FIXME: controlla cont 8 - IVA
                if code in ['2', '3', '6', '7', '10', '11']:
                    parent_id = attivo_id
                elif code in ['21', '23', '24', '26', '27']:
                    parent_id = passivo_id
                elif code in ['61', '62', '63', '64', '65', '69', '71']:
                    parent_id = costi_id
                elif code in ['51', '53', '72']:
                    parent_id = ricavi_id
                elif code in ['52', '68']:
                    parent_id = finanziari_id
                elif code in ['55']:
                    parent_id = straordinari_id
                elif code in ['8']:
                    parent_id = imposte_id
                else:
                    parent_id = 1

            account_id = Account.create (cr, 1, {
                'alawin_nr_corrente': conto.nr_corrente,
                'alawin_codice_fiscale': conto.codice_fiscale,
                'alawin_tipo': conto.tipo,
                'alawin_sotto_tipo': conto.sotto_tipo,
                'alawin_tipo_da': conto.tipo_da,

                'code': code,
                'name': _strip (conto.descrizione),
                'parent_id': parent_id,
                'type': account_type,
                'user_type': user_type_id,
                'currency_mode': 'current',
                'reconcile': reconcile,
                'company_id': 1,
            })

            if code == '6.1':
                conto_clienti_italia = account_id

            if code == '24.1':
                conto_fornitori_italia = account_id

            if code == '51':
                conto_ricavi = account_id

            if code == '61':
                conto_costi = account_id

            account_map[conto.nr_corrente] = account_id

            if not i % 100: print i

        Property = self.pool.get ('ir.property')
        ModelFields = self.pool.get ('ir.model.fields')

        field_account_receivable_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_receivable'),
            ('model', '=', 'res.partner'),
            ('relation', '=', 'account.account'),
        ])[0]

        field_account_payable_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_payable'),
            ('model', '=', 'res.partner'),
            ('relation', '=', 'account.account'),
        ])[0]

        field_account_income_categ_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_income_categ'),
            ('model', '=', 'product.category'),
            ('relation', '=', 'account.account'),
        ])[0]

        field_account_expense_categ_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_expense_categ'),
            ('model', '=', 'product.category'),
            ('relation', '=', 'account.account'),
        ])[0]

        Property.write (cr, 1, Property.search (cr, 1, [
            ('name', '=', 'property_account_receivable'),
            ('company_id', '=', 1),
            ('fields_id', '=', field_account_receivable_id),
            ('res_id', '=', False),
        ]), {
            'value_reference': 'account.account,%d' % conto_clienti_italia
        })

        Property.write (cr, 1, Property.search (cr, 1, [
            ('name', '=', 'property_account_payable'),
            ('company_id', '=', 1),
            ('fields_id', '=', field_account_payable_id),
            ('res_id', '=', False),
        ]), {
            'value_reference': 'account.account,%d' % conto_fornitori_italia
        })

        Property.write (cr, 1, Property.search (cr, 1, [
            ('name', '=', 'property_account_income_categ'),
            ('company_id', '=', 1),
            ('fields_id', '=', field_account_income_categ_id),
            ('res_id', '=', False),
        ]), {
            'value_reference': 'account.account,%d' % Account.create (cr, 1, {
                'code': '51.100',
                'name': 'servizi c/vendite',
                'parent_id': conto_ricavi,
                'type': 'other',
                'user_type': account_type_map['Income'],
                'currency_mode': 'current',
                'company_id': 1,
            }),
        })

        Property.write (cr, 1, Property.search (cr, 1, [
            ('name', '=', 'property_account_expense_categ'),
            ('company_id', '=', 1),
            ('fields_id', '=', field_account_expense_categ_id),
            ('res_id', '=', False),
        ]), {
            'value_reference': 'account.account,%d' % Account.create (cr, 1, {
                'code': '61.100',
                'name': 'servizi c/acquisti',
                'parent_id': conto_costi,
                'type': 'other',
                'user_type': account_type_map['Expense'],
                'currency_mode': 'current',
                'company_id': 1,
            }),
        })

        Account._parent_store_compute (cr)

