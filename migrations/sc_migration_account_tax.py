# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import Iva
from ..db_sc import ScAccount

from .base import Base
from .base import _strip

from slugify import slugify

from decimal import Decimal
from collections import Counter


class sc_migration_account_tax_code (osv.Model, Base):

    _name = 'account.tax.code'
    _inherit = 'account.tax.code'

    _columns = {
    }


class sc_migration_account_tax (osv.Model, Base):

    _name = 'account.tax'
    _inherit = 'account.tax'

    _columns = {
        'alawin_codice_iva': fields.integer ('Alawin codice_iva'),
        'alawin_perc_indetraibilita': fields.float ('Alawin perc_indetraibilita'),
        'alawin_pro_rata': fields.boolean ('Alawin pro_rata'),
        'alawin_sospesa': fields.boolean ('Alawin sospesa'),
    }

    def _import_data (self, cr):
        Tax = self.pool.get ('account.tax')
        TaxCode = self.pool.get ('account.tax.code')

        print "Importing Taxes..."

        default_sale_tax = None
        default_purchase_tax = None

        iva_conto_vendite = self.iva_conto_vendite
        iva_conto_acquisti = self.iva_conto_acquisti

        if len (Tax.search (cr, 1, [])):
            return

        tax_code_map = self.get_tax_code_map ()
        ive = self.alawin_session.query (Iva).all ()

        print "%d Ive" % len (ive)

        iva_counter = Counter ()
        code_map = {}

        for i, iva in enumerate (ive):
            name = _strip (iva.descrizione)

            iva_counter[name] += 1
            if iva_counter[name] > 1:
                name += ' - %d' % iva_counter[name]

            slug = slugify (name)

            if iva.perc_indetraibilita:
                perc_detraibilita = 100 - iva.perc_indetraibilita

                tax_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVC%ddet%d-%s' % (iva.aliquota, perc_detraibilita, slug),
                    'name': 'IVA a credito %d%% detraibile %d%% - %s' % (iva.aliquota, perc_detraibilita, name),
                    'parent_id': tax_code_map['IVC'],
                })

                base_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVC%dIdet%d-%s' % (iva.aliquota, perc_detraibilita, slug),
                    'name': 'IVA a credito %d%% detraibile %d%% (imponibile) - %s' % (iva.aliquota, perc_detraibilita, name),
                    'parent_id': tax_code_map['IVCI'],
                })

                indetr_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVC%dNdet%d-%s' % (iva.aliquota, perc_detraibilita, slug),
                    'name': 'IVA a credito %d%% detraibile %d%% (indetraibile) - %s' % (iva.aliquota, perc_detraibilita, name),
                    'parent_id': tax_code_map['IVCN'],
                })

                code_map[(iva.aliquota, iva.perc_indetraibilita)] = [tax_code_id, base_code_id, indetr_code_id]

                type_tax_use = 'purchase'

                # hack to handle ESCL.ART.26 VEN
                if iva.codice_iva == 35:
                    type_tax_use = 'sale'

                tax_id = Tax.create (cr, 1, {
                    'alawin_codice_iva': iva.codice_iva,
                    'alawin_perc_indetraibilita': iva.perc_indetraibilita,
                    'alawin_pro_rata': True if iva.pro_rata == 'S' else False,
                    'alawin_sospesa': True if iva.sospesa == 'S' else False,

                    'type': 'percent',
                    'name': name,
                    'description': name,
                    'amount': int (iva.aliquota) / Decimal (100),
                    'child_depend': True,
                    'type_tax_use': type_tax_use,
                    'account_collected_id': None,
                    'account_paid_id': None,
                    'base_code_id': base_code_id,
                    'tax_code_id': None,
                    'ref_base_code_id': base_code_id,
                    'ref_tax_code_id': None,
                    'base_sign': -1,
                    'tax_sign': -1,
                    'ref_base_sign': 1,
                    'ref_tax_sign': 1,
                })

                Tax.create (cr, 1, {
                    'parent_id': tax_id,
                    'type': 'percent',
                    'name': name + ' (I)',
                    'description': name + ' (I)',
                    'amount': Decimal ('%.2f' % iva.perc_indetraibilita) / Decimal (100),
                    'sequence': 100,
                    'account_collected_id': None,
                    'account_paid_id': None,
                    'base_code_id': None,
                    'tax_code_id': indetr_code_id,
                    'ref_base_code_id': None,
                    'ref_tax_code_id': indetr_code_id,
                    'base_sign': -1,
                    'tax_sign': -1,
                    'ref_base_sign': 1,
                    'ref_tax_sign': 1,
                })

                Tax.create (cr, 1, {
                    'parent_id': tax_id,
                    'type': 'balance',
                    'name': name + ' (D)',
                    'description': name + ' (D)',
                    'amount': 0,
                    'sequence': 200,
                    'account_collected_id': iva_conto_acquisti.id,
                    'account_paid_id': iva_conto_acquisti.id,
                    'base_code_id': None,
                    'tax_code_id': tax_code_id,
                    'ref_base_code_id': None,
                    'ref_tax_code_id': tax_code_id,
                    'base_sign': -1,
                    'tax_sign': -1,
                    'ref_base_sign': 1,
                    'ref_tax_sign': 1,
                })

            else:
                tax_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVD%d-%s' % (iva.aliquota, slug),
                    'name': 'IVA a debito %d%% - %s' % (iva.aliquota, name),
                    'parent_id': tax_code_map['IVD'],
                })

                base_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVD%dI-%s' % (iva.aliquota, slug),
                    'name': 'IVA a debito %d%% (imponibile) - %s' % (iva.aliquota, name),
                    'parent_id': tax_code_map['IVDI'],
                })

                tax_id = Tax.create (cr, 1, {
                    'alawin_codice_iva': iva.codice_iva,
                    'alawin_pro_rata': True if iva.pro_rata == 'S' else False,
                    'alawin_sospesa': True if iva.sospesa == 'S' else False,

                    'type': 'percent',
                    'name': name + '(debito)',
                    'description': name,
                    'amount': int (iva.aliquota) / Decimal (100),
                    'child_depend': False,
                    'type_tax_use': 'sale',
                    'account_collected_id': iva_conto_vendite.id,
                    'account_paid_id': iva_conto_vendite.id,
                    'base_code_id': base_code_id,
                    'tax_code_id': tax_code_id,
                    'ref_base_code_id': base_code_id,
                    'ref_tax_code_id': tax_code_id,
                    'base_sign': 1,
                    'tax_sign': 1,
                    'ref_base_sign': -1,
                    'ref_tax_sign': -1,
                })

                if iva.codice_iva == 90: # Iva 22%
                    default_sale_tax = tax_id

                tax_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVC%d-%s' % (iva.aliquota, slug),
                    'name': 'IVA a credito %d%% - %s' % (iva.aliquota, name),
                    'parent_id': tax_code_map['IVC'],
                })

                base_code_id = TaxCode.create (cr, 1, {
                    'code': 'IVC%dI-%s' % (iva.aliquota, slug),
                    'name': 'IVA a credito %d%% (imponibile) - %s' % (iva.aliquota, name),
                    'parent_id': tax_code_map['IVCI'],
                })

                tax_id = Tax.create (cr, 1, {
                    'alawin_codice_iva': iva.codice_iva,
                    'alawin_pro_rata': True if iva.pro_rata == 'S' else False,
                    'alawin_sospesa': True if iva.sospesa == 'S' else False,

                    'type': 'percent',
                    'name': name + '(credito)',
                    'description': name,
                    'amount': int (iva.aliquota) / Decimal (100),
                    'child_depend': False,
                    'type_tax_use': 'purchase',
                    'account_collected_id': iva_conto_acquisti.id,
                    'account_paid_id': iva_conto_acquisti.id,
                    'base_code_id': base_code_id,
                    'tax_code_id': tax_code_id,
                    'ref_base_code_id': base_code_id,
                    'ref_tax_code_id': tax_code_id,
                    'base_sign': -1,
                    'tax_sign': -1,
                    'ref_base_sign': 1,
                    'ref_tax_sign': 1,
                })

                if iva.codice_iva == 90: # Iva 22%
                    default_purchase_tax = tax_id

        self.update_settings (cr, {
            'default_sale_tax': default_sale_tax,
            'default_purchase_tax': default_purchase_tax,
        })

