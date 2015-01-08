# -*- coding: utf-8 -*-

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import DeferredReflection


AlawinBase = declarative_base (cls=DeferredReflection)


class Nazioni (AlawinBase):
    __tablename__ = 'nazioni'


class Regioni (AlawinBase):
    __tablename__ = 'regioni'


class ClientiFornitori (AlawinBase):
    __tablename__ = 'clienti_fornitori'

    nr_corrente = Column (String, ForeignKey ('sottoconti.nr_corrente'), primary_key=True)
    documenti = relationship ('Documento', backref='cliente_fornitore',
        primaryjoin='ClientiFornitori.nr_corrente == foreign(Documento.interstatario)')


class ClientiFornitoriComuna (AlawinBase):
    __tablename__ = 'clienti_fornitori_comuna'

    codice_fiscale = Column (String, primary_key=True)


class Articoli (AlawinBase):
    __tablename__ = 'articoli'

    riga_documento = relationship ('DocumentoRighe', backref='articolo')


class Gruppi (AlawinBase):
    __tablename__ = 'gruppi'

    articoli = relationship ('Articoli', backref='gruppo')


class PianoConti (AlawinBase):
    __tablename__ = 'piano_conti'

    nr_corrente = Column (Integer, primary_key=True)
    nr_corrente_par = Column (Integer, ForeignKey ('piano_conti.nr_corrente'))
    parent = relationship ('PianoConti', backref='children', remote_side=[nr_corrente])
    detail = relationship ('Sottoconti', uselist=False, backref='base')
    cliente_fornitore_comuna = relationship ('ClientiFornitoriComuna',
        primaryjoin='ClientiFornitoriComuna.codice_fiscale == foreign(PianoConti.codice_fiscale)',
        backref='conti')
    progressivi = relationship ('Progressivi')
    righe_documenti = relationship ('DocumentoRighe', backref='conto')


class Sottoconti (AlawinBase):
    __tablename__ = 'sottoconti'

    nr_corrente = Column (String, ForeignKey ('piano_conti.nr_corrente'), primary_key=True)
    cliente_fornitore = relationship ('ClientiFornitori', uselist=False, backref='sottoconto')


class Progressivi (AlawinBase):
    __tablename__ = 'progressivi'

    nr_corrente = Column (String, ForeignKey ('piano_conti.nr_corrente'))


class CausaliTesta (AlawinBase):
    __tablename__ = 'causali_testa'


class CausaliRighe (AlawinBase):
    __tablename__ = 'causali_righe'


class MovimentiTesta (AlawinBase):
    __tablename__ = 'movimenti_testa'

    righe = relationship ('MovimentiRighe', backref='testa')
    id_doc = Column (Integer, ForeignKey ('documento.num_documento'))


class MovimentiRighe (AlawinBase):
    __tablename__ = 'movimenti_righe'

    # FIXME: set primary_key=True, otherwise test.righe doesn't work right...
    nr_mov = Column (Integer, ForeignKey ('movimenti_testa.nr_mov'), primary_key=True)
    sottoconto = Column (Integer, ForeignKey ('sottoconti.nr_corrente'))
    conto = relationship ('Sottoconti', backref='righe')


#class Banche (AlawinBase):
#    __tablename__ = 'banche'
#
#    agenzie = relationship ('Agenzie')
#
#
#class Agenzie (AlawinBase):
#    __tablename__ = 'agenzie'
#
#    banca = Column (String, ForeignKey ('banche.cod_abi'))


class TipiDocumento (AlawinBase):
    __tablename__ = 'tipi_documento'

    documenti = relationship ('Documento', backref='tipo_documento_ref')


class Documento (AlawinBase):
    __tablename__ = 'documento'

    num_documento = Column (Integer, primary_key=True)
    codice_tipo_documento = Column (Integer, ForeignKey ('tipi_documento.codice'))
    righe = relationship ('DocumentoRighe', backref='documento')
    interstatario = Column (Integer, ForeignKey ('clienti_fornitori.nr_corrente'), primary_key=True)
    movimento_testa = relationship ('MovimentiTesta', uselist=False, backref='doc')


class DocumentoRighe (AlawinBase):
    __tablename__ = 'documento_righe'

    num_documento = Column (Integer, ForeignKey ('documento.num_documento'), primary_key=True)
    codce_ex = Column (Integer, ForeignKey ('articoli.cod_art'), primary_key=True)


class Iva (AlawinBase):
    __tablename__ = 'iva'


class CentroCosto (AlawinBase):
    __tablename__ = 'centro_costo'


class CondPagamTesta (AlawinBase):
    __tablename__ = 'cond_pagam_testa'

    righe = relationship ('CondPagamRighe', backref='condizione')


class CondPagamRighe (AlawinBase):
    __tablename__ = 'cond_pagam_righe'

