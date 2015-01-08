delete from account_tax_code where parent_id is not null and parent_id != 1;
delete from account_tax;
delete from account_invoice;
delete from account_move;
delete from account_model;
delete from account_analytic_line where general_account_id = 131;
update account_analytic_line set general_account_id = 1;
delete from account_account where id > 1;
delete from res_partner where id > 104; -- FIXME check last id
delete from account_payment_term;

-- Fix journals:
--   * create journals
--   * create analytic journals
--   * set default analytic journal
--   * Opening Journal: unflag "centralized" or set default debit/credit accounts

