# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import Nazioni
from ..db_sc import ScCountry

from .base import Base
from .base import _strip

import fuzzywuzzy.process


class sc_migration_country (osv.Model, Base):

    _name = 'res.country'
    _inherit = 'res.country'

    _columns = {
        'alawin_id': fields.integer ('Alawin id'),
        'alawin_stato': fields.text ('Alawin stato'),
        'alawin_descrizione': fields.text ('Alawin descrizione'),
    }

    def _import_data (self, cr):
        print "Importing Countries..."

        Country = self.pool.get ('res.country')

        if Country.search (cr, 1, [('alawin_id', '!=', False)]):
            return

        nazioni = self.alawin_session.query (Nazioni).all ()

        sc_session = self.ScSession ()

        countries = sc_session.query (ScCountry).all ()
        country_names = [c.name for c in countries]

        country_map = {
            'ITALIA': 'Italy',
            'USA': 'United States',
            'U.K.': 'United Kingdom',
            'SLOVAK REPUBLIC': 'Slovakia',
            'UCRAINA': 'Ukraine',
           u'GUYANE FRANÃAISE': 'French Guyana',
            'REPUBLIC OF KOREA': 'South Korea',
            'LIBIA': 'Libya',
            'CITTA DEL VATICANO': 'Holy See (Vatican City State)',
        }

        for nazione in nazioni[:]:
            nome = nazione.descrizione.strip ()

            if nome in country_map:
                found, score = country_map[nome], 100
            else:
                found, score = fuzzywuzzy.process.extractOne (nome, country_names)

            if score > 80:
                country = countries[country_names.index (found)]

                country.alawin_id = nazione.id_ai
                country.alawin_descrizione = nome
                country.alawin_stato = _strip (nazione.stato)

                nazioni.remove (nazione)
            else:
                print "Not found: ", nome

        sc_session.commit ()

