# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import PianoConti
from ..db_alawin import ClientiFornitoriComuna

from .base import Base
from .base import _strip
from .base import _rstrip

from collections import Counter


class sc_migration_partner (osv.Model, Base):

    _name = 'res.partner'
    _inherit = 'res.partner'

    def check_vat (self, cr, uid, ids, context=None):
        return True

    _constraints = [(check_vat, None, ["vat"])] # disable vat check

    _columns = {
        'alawin_codice_fiscale': fields.text ('Alawin codice_fiscale'),
        'alawin_partita_iva': fields.text ('Alawin iva'),
    }

    _sql_constraints = [ 
        ('unique_alawin_codice_fiscale', 'unique(alawin_codice_fiscale)',
         'Partner with matching Alawin codice_fiscale'),
    ]

    def _import_data (self, cr):
        print "Importing Partners..."

        Partner = self.pool.get ('res.partner')
        Property = self.pool.get ('ir.property')
        ModelFields = self.pool.get ('ir.model.fields')

        if Partner.search (cr, 1, [('alawin_codice_fiscale', '!=', False)]):
            return

        province_map = self.get_province_map ()
        region_id_map = self.get_region_id_map ()
        country_id_map = self.get_country_id_map ()
        country_code_map = self.get_country_code_map ()
        account_id_map = self.get_account_id_map ()

        field_account_receivable_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_receivable'),
            ('model', '=', 'res.partner'),
        ])[0]

        field_account_payable_id = ModelFields.search (cr, 1, [
            ('name', '=', 'property_account_payable'),
            ('model', '=', 'res.partner'),
        ])[0]

        movimenti = self.get_chosen_moves ()
        documenti = self.get_chosen_invoices ()

        conti = self.alawin_session.query (PianoConti).filter (
            PianoConti.nr_corrente.in_ (
                [m.intestatario for m in movimenti if m.intestatario]
                +
                sum ([[r.sottoconto for r in m.righe] for m in movimenti], [])
                +
                [d.interstatario for d in documenti if d.interstatario]
            ),
        ).all ()

        clienti = self.alawin_session.query (ClientiFornitoriComuna).filter (
            ClientiFornitoriComuna.codice_fiscale.in_ ([c.codice_fiscale for c in conti if c.codice_fiscale]),
        ).all ()

        print "%d Clienti" % len (clienti)

        not_found = []
        name_counter = Counter ()
        for i, cliente in enumerate (clienti):
            name = _strip (cliente.ragione_sociale)
            if cliente.ragione_sociale2 and _strip (cliente.ragione_sociale2):
                name += ', %s' % _strip (cliente.ragione_sociale2)

            # heuristic value
            is_company = True if _strip (cliente.ragione_sociale2) else False

            name_counter[name] += 1
            if name_counter[name] > 1:
                name += ' - %d' % name_counter[name]

            vat = _strip (cliente.partita_iva)
            if vat:
                vat = (country_code_map.get (cliente.nazione) or 'IT') + _strip (vat.upper ())

            conto_cliente = self.get_conto_cliente (cliente.codice_fiscale)
            conto_fornitore = self.get_conto_fornitore (cliente.codice_fiscale)

            partner_id = Partner.create (cr, 1, {
                'alawin_codice_fiscale': cliente.codice_fiscale,
                'alawin_partita_iva': _strip (cliente.partita_iva),

                'name': name,
                'fiscalcode': cliente.codice_fiscale,
                'vat': vat,
                'is_company': is_company,
                'street': _strip (cliente.via),
                'zip': _strip (cliente.cap),
                'city': _strip (cliente.citta),
                'province': province_map.get (_strip (cliente.provincia)),
                'region': region_id_map.get (cliente.id_regione) if cliente.id_regione else None,
                'country_id': country_id_map.get (cliente.nazione) if cliente.nazione else None,
                'phone': _strip (cliente.telefono),
                'fax': _strip (cliente.fax),
                'mobile': _strip (cliente.celulare),
                'email': _strip (cliente.imail),
                'birthdate': cliente.data_nascita,
                'customer': True if conto_cliente else False,
                'supplier': True if conto_fornitore else False,
                'notification_email_send': 'none',
            })

            account_receivable = account_payable = None

            if conto_fornitore:
                account_payable = account_id_map[conto_fornitore.nr_corrente]
                if not conto_cliente:
                    account_receivable = {
                        '24.1': self.get_conto ('6.1'),
                        '24.2': self.get_conto ('6.2'),
                        '24.3': self.get_conto ('6.3'),
                    }[_strip (conto_fornitore.codice)].id

            if conto_cliente:
                account_receivable = account_id_map[conto_cliente.nr_corrente]
                if not conto_fornitore:
                    account_payable = {
                        '6.1': self.get_conto ('24.1'),
                        '6.2': self.get_conto ('24.2'),
                        '6.3': self.get_conto ('24.3'),
                    }[_strip (conto_cliente.codice)].id

            if account_receivable:
                property_id = Property.create (cr, 1, {
                    'name': 'property_account_receivable',
                    'company_id': '1',
                    'fields_id': field_account_receivable_id,
                    'value_reference': 'account.account,%d' % account_receivable,
                    'res_id': 'res.partner,%d' % partner_id,
                })

            if account_payable:
                property_id = Property.create (cr, 1, {
                    'name': 'property_account_payable',
                    'company_id': '1',
                    'fields_id': field_account_payable_id,
                    'value_reference': 'account.account,%d' % account_payable,
                    'res_id': 'res.partner,%d' % partner_id,
                })

            if not i % 10: print "Cliente", i

        print "NOT FOUND CLIENTI", not_found

