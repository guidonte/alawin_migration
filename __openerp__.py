{
    'name': 'Alawin migration to OpenERP',
    'description': 'Migration from Alawin software to OpenERP',
    'author': 'Goodora s.r.l.',
    'version': '0.1',
    'category': 'Hidden',
    'depends': [
        'l10n_it_base',
        'l10n_it_fiscalcode',
#        'l10n_it_partially_deductible_vat',
#        'l10n_it_vat_registries',
##        'l10n_it_ricevute_bancarie',
##        'l10n_it_withholding_tax',
#        'account_fiscal_year_closing',
#        'account_vat_period_end_statement',
        'base_vat',
        'account_tweaks',
    ],
    'data': [
        'migration.xml',
    ],
    'installable': True,
    'auto_install': False,
}

