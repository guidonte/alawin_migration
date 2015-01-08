# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import CentroCosto
from ..db_alawin import Gruppi
from ..db_alawin import Articoli

from .base import Base
from .base import _strip

from sqlalchemy import or_

import fuzzywuzzy.process


class sc_migration_category (osv.Model, Base):

    _name = 'product.category'
    _inherit = 'product.category'

    _columns = {
        'alawin_id_grup': fields.integer ('Alawin id_grup'),
    }


class sc_migration_product (osv.Model, Base):

    _name = 'product.product'
    _inherit = 'product.product'

    _columns = {
        'alawin_cod_art': fields.integer ('Alawin cod_art'),
        'alawin_codice_articol': fields.text ('Alawin codice_articol'),
        'alawin_sottoc_vendite': fields.text ('Alawin sottoc_vendite'),

        'alawin_analytic_account_id': fields.many2one ('account.analytic.account', ondelete='set null'),
    }


class sc_migration_analytic_account (osv.Model, Base):

    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    _columns = {
        'alawin_id_costo': fields.integer ('Alawin id_costo'),
        'alawin_codice': fields.text ('Alawin codice'),
        'alawin_id_grup': fields.integer ('Alawin id_grup'),
        'alawin_cod_art': fields.integer ('Alawin cod_art'),
    }

    def _import_articoli (self, cr):
        AnalyticAccount = self.pool.get ('account.analytic.account')
        Category = self.pool.get ('product.category')
        ProductTemplate = self.pool.get ('product.template')
        Product = self.pool.get ('product.product')
        Property = self.pool.get ('ir.property')
        ModelFields = self.pool.get ('ir.model.fields')

        analytic_accounts = AnalyticAccount.browse (cr, 1,
            AnalyticAccount.search (cr, 1, [('alawin_id_grup', '!=', False)]))

        account_map = dict ([(a.alawin_id_grup, a.id) for a in analytic_accounts])
        category_map = dict ([(c.alawin_id_grup, c) for c in
            Category.browse (cr, 1, Category.search (cr, 1, []))])
        iva_id_map = self.get_iva_id_map ()
        general_account_id_map = self.get_account_id_map ()

        articoli = self.alawin_session.query (Articoli).filter (
            Articoli.codice_ditta=='1',
            Articoli.id_grup.in_ (account_map.keys ()),
        ).all ()

        articoli += self.alawin_session.query (Articoli).filter (
            Articoli.codice_articol.in_ ([
                '14CAUZIONI',
                '14HOSTESS',
                '14HOSTESSBIS',
            ]),
        ).all ()

        essxxrc_item = self.alawin_session.query (Articoli).filter (
            Articoli.codice_articol=='14ESSXXRCTO6').all ()[0]

        essxxrc_item.id_grup = 330 # 14_ESSXXRC

        articoli.append (essxxrc_item)

        account_map[86] = AnalyticAccount.search (cr, 1,
            [('name', '=', 'Centri di Ricavo')])[0]

        print "%d Articoli" % len (articoli)

        for i, articolo in enumerate (articoli):
            account_id = AnalyticAccount.create (cr, 1, {
                'alawin_cod_art': articolo.cod_art,

                'name': '%s - %s' % (_strip (articolo.codice_articol), _strip (articolo.descrizione)),
                'type': 'normal',
                'parent_id': account_map[articolo.id_grup],
                'state': 'open',
                'company_id': 1,
            })

            category = category_map.get (articolo.id_grup)
            if not category:
                continue

            cod_iva = articolo.cod_iva_proponere_fat
            iva_id = iva_id_map[(cod_iva, 'sale')] if cod_iva else None

            tmpl_id = ProductTemplate.create (cr, 1, {
                'name': _strip (articolo.descrizione),
                'type': 'service',
                'categ_id': category.id,
                'taxes_id': [(4, iva_id)] if iva_id else None,
                #'list_price':
            })

            if articolo.sottoc_vendite:
                field_id = ModelFields.search (cr, 1, [
                    ('name', '=', 'property_account_income'),
                    ('model', '=', 'product.template'),
                ])[0]

                property_id = Property.create (cr, 1, {
                    'name': 'property_account_income',
                    'company_id': '1',
                    'fields_id': field_id,
                    'value_reference': 'account.account,%d' % general_account_id_map[articolo.sottoc_vendite],
                    'res_id': 'product.template,%d' % tmpl_id,
                })

                field_id = ModelFields.search (cr, 1, [
                    ('name', '=', 'property_analytic_account_income'),
                    ('model', '=', 'product.template'),
                ])[0]

                property_id = Property.create (cr, 1, {
                    'name': 'property_analytic_account_income',
                    'company_id': '1',
                    'fields_id': field_id,
                    'value_reference': 'account.analytic.account,%d' % account_id,
                    'res_id': 'product.template,%d' % tmpl_id,
                })

            product_id = Product.create (cr, 1, {
                'alawin_cod_art': articolo.cod_art,
                'alawin_codice_articol': _strip (articolo.codice_articol),
                'alawin_sottoc_vendite': articolo.sottoc_vendite,

                'product_tmpl_id': tmpl_id,
                'name': _strip (articolo.descrizione),
            })

            if not i % 10: print "Articolo", i

    def _import_gruppi (self, cr):
        AnalyticAccount = self.pool.get ('account.analytic.account')
        Category = self.pool.get ('product.category')

        gruppi = self.alawin_session.query (Gruppi).filter (
            Gruppi.codice_ditta=='1',
            or_ (Gruppi.descrizione.like ('14_%'),
                 Gruppi.descrizione.like ('15_%')),
        ).all ()

        print "%d Gruppi" % len (gruppi)

        analytic_accounts = AnalyticAccount.browse (cr, 1,
            AnalyticAccount.search (cr, 1, [('type', '=', 'contract')]))

        account_map = dict ([(_strip (a.name), a) for a in analytic_accounts])

        progetti_id = Category.create (cr, 1, {
            'name': 'Progetti 2014',
        })

        for gruppo in gruppi[:]:
            tokens = _strip (gruppo.descrizione).split ('_')

            name = '%s_%s' % ('_'.join (tokens[1:]), tokens[0])

            name_map = {
                'CORSIATU_14': 'CORSO_1_ATU_IPSEN_14',
                'CORSITAKEDA_14': 'CORSO1 TAKEDA_14',
                'MATH_14': 'MATHS_14',
                'MATHS_14': 'MATHS_14',
                'SIR_14': 'SEGRETERIA GENERALE SIR',
            }

            if name in name_map:
                name = name_map[name]

            Category.create (cr, 1, {
                'alawin_id_grup': gruppo.id_grup,

                'name': name,
                'parent_id': progetti_id,
            })

            account = account_map.get (name)
            if not account:
                continue

            gruppi.remove (gruppo)

            account.write ({
                'alawin_id_grup': gruppo.id_grup,
            })

        guessed_groups = []
        for gruppo in gruppi[:]:
            tokens = _strip (gruppo.descrizione).split ('_')

            name = '%s_%s' % ('_'.join (tokens[1:]), tokens[0])

            found, score = fuzzywuzzy.process.extractOne (name, account_map)

            if not found:
                continue

            if score != 100:
                guessed_groups.append ((name, found, score))

            Category.create (cr, 1, {
                'alawin_id_grup': gruppo.id_grup,

                'name': name,
                'parent_id': progetti_id,
            })

            account = account_map.pop (found)
            gruppi.remove (gruppo)

            account.write ({
                'alawin_id_grup': gruppo.id_grup,
            })

        if guessed_groups:
            print "Guessed Groups", guessed_groups

        if gruppi:
            print "Not Found Groups", gruppi

    def _import_data (self, cr):
        print "Importing Analytic Accounts..."

        AnalyticAccount = self.pool.get ('account.analytic.account')

        if AnalyticAccount.search (cr, 1, [('alawin_id_costo', '!=', False)]):
            return

        centri = self.alawin_session.query (CentroCosto).filter (
            CentroCosto.codice_ditta=='1',
            CentroCosto.id_costo_padre!=-1,
        ).order_by (CentroCosto.livello).all ()

        print "%d Centri di costo" % len (centri)

        existing_accounts = self.get_existing_analytic_accounts ()

        projects_id = AnalyticAccount.search (cr, 1, [('name', '=', 'Projects')])[0]
        if not AnalyticAccount.search (cr, 1, [('name', '=', 'Centri di Costo')]):
            centri_di_costo_id = AnalyticAccount.create (cr, 1, {
                'name': 'Centri di Costo',
                'type': 'view',
                'state': 'open',
                'company_id': 1,
            })

        name_map =  {
            'CONGOB_14': "CONGIUNTO_OBESITA'_14",
            'ATU_14': u'ATU società',
            'GUONE_SOC_14': u'GUONE società',
            'C.SO ATU TAKEDA_14': 'CORSO1 TAKEDA_14',
            'SIR_14': 'SEGRETERIA GENERALE SIR',
            'C.SO1ATUIPSEN_14': 'CORSO_1_ATU_IPSEN_14',
            'C.SO ATUIPSEN1_14': 'CORSO_1_ATU_IPSEN_14',
            'C.SO ATUIPSEN2_14': 'CORSO_2_ATU_IPSEN_14',
            'C.SO ATUIPSEN3_14': 'CORSO_3_ATU_IPSEN_14',
            'C.SO ATUIPSEN4_14': 'CORSO_4_ATU_IPSEN_14',
            'ARNEG_25_08_14': 'ARNEG 25.08_14',
            'TRIVENETA_14': 'SEGRETERIA GENERALE ATU',
            'ESSDERC_14': 'ESSXXRC_14',
            'ESSEDERC_14': 'ESSXXRC_14',
            'OBESITA_14': "CONGIUNTO_OBESITA'_14",
            'C.SO UROPN_14': 'CORSO ASTELLAS UROPN_14',
            'FOOTHILL_14': 'Tickets_14 (Foothill)',
            'OHIO-WES_14': 'AAA OhioSLOWFOOD_14',
        }

        account_map = {}
        n_parents = 0
        not_matched = []
        for i, centro in enumerate (sorted (centri, key=lambda c: (c.livello, c.id_costo))):
            if not i % 100: print i

            code = _strip (centro.codice)
            name = _strip (centro.descrizione) or 'NO NAME'

            if centro.id_costo <= 83 and name != 'Centri di Ricavo':
                name = ' '.join (name.split ()[1:])

            name = name_map.get (name) or name

            account_id = None
            if centro.livello == 1:
                # manually found useless items
                if (not '_14' in centro.descrizione and not '_15' in centro.descrizione) and centro.id_costo > 58:
                    continue

                a_type = 'contract' if centro.id_costo > 58 else 'normal'
                parent_id = projects_id if centro.id_costo > 58 else centri_di_costo_id
                if name == 'Centri di Ricavo':
                    a_type = 'view'
                    parent_id = None

                account_id = existing_accounts.get (name)
                if not account_id:
                    found, score = fuzzywuzzy.process.extractOne (name, existing_accounts)
                    if found and score >= 88:
                        account_id = existing_accounts[found]

                if not account_id:
                    not_matched.append (name)

                n_parents += 1
            else:
                parent_id = account_map.get (centro.id_costo_padre)
                a_type = 'normal'
                if not parent_id:
                    continue

            if account_id:
                AnalyticAccount.write (cr, 1, [account_id], {
                    'alawin_id_costo': centro.id_costo,
                    'alawin_codice': centro.codice,
                })
            else:
                account_id = AnalyticAccount.create (cr, 1, {
                    'alawin_id_costo': centro.id_costo,
                    'alawin_codice': centro.codice,

                    'name': name,
                    'type': a_type,
                    'parent_id': parent_id,
                    'state': 'open',
                    'company_id': 1,
                })

            account_map[centro.id_costo] = account_id

        print "Found %d centri di costo di livello 1" % n_parents
        if not_matched:
            print "Not matched %d centri di costo di livello 1: %s" % (len (not_matched), not_matched)

        self._import_gruppi (cr)
        self._import_articoli (cr)

        cr.execute ('''update account_analytic_line set general_account_id = %d
                       where general_account_id = 1''' % self.conto_acquisti_default.id)

