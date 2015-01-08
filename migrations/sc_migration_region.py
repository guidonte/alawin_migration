# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields

from ..db_alawin import Regioni

from ..db_sc import ScRegion

from .base import Base
from .base import _strip

import fuzzywuzzy.process


class sc_migration_region (osv.Model, Base):

    _name = 'res.region'
    _inherit = 'res.region'

    _columns = {
        'alawin_id': fields.integer ('Alawin id'),
        'alawin_regione': fields.text ('Alawin regione'),
    }

    def _import_data (self, cr):
        print "Importing Regions..."

        Region = self.pool.get ('res.region')

        regioni = self.alawin_session.query (Regioni).all ()

        sc_session = self.ScSession ()

        regions = sc_session.query (ScRegion).all ()
        region_names = [r.name for r in regions]

        region_map = {
            'TRENTO': 'Trentino-Alto Adige',
            'BOLZANO': 'Trentino-Alto Adige',
        }

        for regione in regioni[:]:
            nome = regione.regione.strip ()

            if nome in region_map:
                found, score = region_map[nome], 100
            else:
                found, score = fuzzywuzzy.process.extractOne (nome, region_names)

            if score > 80:
                region = regions[region_names.index (found)]

                region.alawin_id = regione.id_regione
                region.alawin_regione = nome

                regioni.remove (regione)
            else:
                print "Not found: ", nome

        sc_session.commit ()

