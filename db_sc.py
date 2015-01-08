# -*- coding: utf-8 -*-

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import DeferredReflection


ScBase = declarative_base (cls=DeferredReflection)


class ScPeriod (ScBase):
    __tablename__ = 'account_period'


class ScPartner (ScBase):
    __tablename__ = 'res_partner'


class ScCountry (ScBase):
    __tablename__ = 'res_country'


class ScRegion (ScBase):
    __tablename__ = 'res_region'


class ScProvince (ScBase):
    __tablename__ = 'res_province'


class ScProduct (ScBase):
    __tablename__ = 'product_product'


class ScAnalyticAccount (ScBase):
    __tablename__ = 'account_analytic_account'


class ScAccount (ScBase):
    __tablename__ = 'account_account'


class ScJournal (ScBase):
    __tablename__ = 'account_journal'


class ScAccountMove (ScBase):
    __tablename__ = 'account_move'

    lines = relationship ('ScAccountMoveLine', backref='move')


class ScAccountMoveLine (ScBase):
    __tablename__ = 'account_move_line'

    move_id = Column (Integer, ForeignKey ('account_move.id'), primary_key=True)


class ScAccountModel (ScBase):
    __tablename__ = 'account_model'

    lines = relationship ('ScAccountModelLine', backref='model')


class ScAccountModelLine (ScBase):
    __tablename__ = 'account_model_line'

    model_id = Column (Integer, ForeignKey ('account_model.id'), primary_key=True)


class ScAccountTax (ScBase):
    __tablename__ = 'account_tax'


class ScAccountTaxCode (ScBase):
    __tablename__ = 'account_tax_code'


class ScPaymentTerm (ScBase):
    __tablename__ = 'account_payment_term'

