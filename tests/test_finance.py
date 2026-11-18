"""Regras financeiras, migração, backup e precisão; banco temporário, sem rede."""
import csv
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from holy_planner.backend import Api
from holy_planner.database import Database
from holy_planner.finance import money_cents


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.api = Api(self.path)
        self.month = '2026-01'

    def tearDown(self):
        self.temp.cleanup()

    def add(self, kind='income', amount='100,00', **extra):
        payload = dict(title='Movimento', kind=kind, amount=amount, day='2026-01-02',
                       category='Outros', status='paid', asset='CDB')
        payload.update(extra)
        result = self.api.save_transaction(payload)
        self.assertTrue(result['ok'], result)
        return result['id']

    def snapshot(self):
        return self.api.finance_snapshot(self.month)

    def test_exact_cents_and_brazilian_input(self):
        self.assertEqual(money_cents('1.234,56'), 123456)
        self.assertEqual(money_cents('1234.56'), 123456)
        self.assertEqual(money_cents('0,01'), 1)
        self.assertEqual(money_cents(12), 1200)
        for value in ('NaN','Infinity','1e3','1,234','1.234','1,23,45','12.34,56',
                      True, 12.34, None, '', '-1', '0', '1000000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money_cents(value)
        for n in range(10):
            self.add(amount='0,10', title=str(n))
        self.assertEqual(self.snapshot()['cash_cents'], 100)

    def test_balances_history_and_investment_transfers(self):
        self.assertTrue(self.api.save_finance_settings({'opening_cash':'1000', 'opening_invested':'2000'})['ok'])
        self.add(amount='1000', day='2025-12-01')
        self.add('expense','200',day='2025-12-02')
        self.add('investment','300',day='2025-12-03')
        self.add('income','5000')
        self.add('expense','1200')
        self.add('investment','1000')
        self.add('redemption','200')
        self.add('yield','50')
        self.add('expense','400',status='pending')
        self.add('income','200',status='pending')
        f = self.snapshot()
        self.assertEqual(f['cash_cents'],455000)
        self.assertEqual(f['invested_cents'],310000)
        self.assertEqual(f['net_month_cents'],305000)
        self.assertEqual(f['projected_cash_cents'],435000)
        self.assertEqual(f['assets'][0]['net_cents'],110000)
        self.assertEqual(f['assets'][0]['yield_cents'],5000)
        self.assertEqual(f['totals']['income'],500000)
        self.assertEqual(f['totals']['expense'],120000)
        self.assertEqual(f['trend'][-2]['income_cents'],100000)
        self.assertEqual(f['trend'][-1]['income_cents'],505000)

    def test_pending_never_changes_real_balance_and_toggle_reverses(self):
        item = self.add('expense','99,90',status='pending')
        f=self.snapshot()
        self.assertEqual(f['cash_cents'],0)
        self.assertEqual(f['projected_cash_cents'],-9990)
        self.assertTrue(self.api.toggle_transaction(item)['ok'])
        self.assertEqual(self.snapshot()['cash_cents'],-9990)
        self.api.toggle_transaction(item)
        self.assertEqual(self.snapshot()['cash_cents'],0)

    def test_future_paid_rejected_but_planned_allowed(self):
        future=(date.today()+timedelta(days=1)).isoformat()
        payload=dict(title='Futuro',kind='income',amount='10',day=future,category='Outros',status='paid')
        self.assertFalse(self.api.save_transaction(payload)['ok'])
        payload['status']='pending'
        item=self.api.save_transaction(payload)['id']
        self.assertFalse(self.api.toggle_transaction(item)['ok'])

    def test_edit_delete_reopen_persist(self):
        item=self.add()
        payload=dict(title='Alterado',kind='expense',amount='22,15',day='2026-01-10',category='Saúde',status='paid')
        self.assertTrue(self.api.save_transaction(payload,item)['ok'])
        other=Api(self.path)
        self.assertEqual(other.finance_snapshot(self.month)['cash_cents'],-2215)
        self.assertTrue(other.delete_finance('finance_transactions',item)['ok'])
        self.assertEqual(self.snapshot()['transactions'],[])
        self.assertFalse(self.api.save_transaction(payload,item)['ok'])
        self.assertFalse(self.api.delete_finance('finance_transactions',item)['ok'])

    def test_validation_rejects_invalid_fields_without_writing(self):
        good=dict(title='Valid',kind='income',amount='10',day='2026-01-10',category='Outros')
        for key,value in [('title',' '),('title','x'*201),('kind','other'),('kind',[]),
                          ('amount',True),('amount','1.001'),('day','2026-02-31'),
                          ('day','20260101'),('status','other'),('category',''),
                          ('category',None),('notes','x'*10001),('account',12)]:
            with self.subTest(key=key,value=str(value)[:20]):
                self.assertFalse(self.api.save_transaction({**good,key:value})['ok'])
        for kind in ('investment','redemption','yield'):
            self.assertFalse(self.api.save_transaction({**good,'kind':kind})['ok'])
        for invalid in (None,[],True):
            self.assertFalse(self.api.save_transaction(invalid)['ok'])
        for invalid in (True,-1,1.5,'1.0',999):
            self.assertFalse(self.api.toggle_transaction(invalid)['ok'])
            self.assertFalse(self.api.delete_finance('finance_transactions',invalid)['ok'])
        self.assertFalse(self.api.delete_finance('tasks',1)['ok'])
        self.assertEqual(self.snapshot()['transactions'],[])

    def test_budget_case_insensitive_upsert_and_pending_separate(self):
        p={'month':self.month,'category':'Alimentação','amount':'100'}
        self.assertTrue(self.api.save_budget(p)['ok'])
        self.assertTrue(self.api.save_budget({**p,'category':'alimentação','amount':'200'})['ok'])
        self.add('expense','50',category='Alimentação')
        self.add('expense','175',category='alimentação',status='pending')
        self.add('investment','500',category='Alimentação')
        b=self.snapshot()['budgets'][0]
        self.assertEqual(len(self.snapshot()['budgets']),1)
        self.assertEqual(b['amount_cents'],20000)
        self.assertEqual(b['spent_cents'],5000)
        self.assertEqual(b['pending_cents'],17500)
        self.assertTrue(self.api.save_budget({**p,'month':'2026-02'})['ok'])
        self.api.delete_finance('finance_budgets',b['id'])
        self.assertEqual(len(self.snapshot()['transactions']),3)

    def test_budget_exceeded_and_duplicate_edit_friendly_error(self):
        self.api.save_budget({'month':self.month,'category':'Lazer','amount':'10'})
        self.api.save_budget({'month':self.month,'category':'Moradia','amount':'100'})
        self.add('expense','11',category='Lazer')
        b=next(b for b in self.snapshot()['budgets'] if b['category']=='Lazer')
        self.assertGreater(b['spent_cents'],b['amount_cents'])
        self.assertFalse(self.api.save_budget({'month':self.month,'category':'Moradia','amount':'10'},b['id'])['ok'])
        self.assertFalse(self.api.save_budget({'month':self.month,'category':'','amount':'1'})['ok'])
        self.assertFalse(self.api.save_budget({'month':'2026-13','category':'Lazer','amount':'1'})['ok'])

    def test_unicode_categories_and_asset_spelling_share_totals(self):
        self.api.save_budget({'month':self.month,'category':'SAÚDE','amount':'100'})
        self.add('expense','25',category='saúde')
        self.add('expense','30',category='SAÚDE')
        self.add('investment','100',asset='CDB Ágil')
        self.add('investment','50',asset='cdb ágil')
        f=self.snapshot()
        self.assertEqual(f['budgets'][0]['spent_cents'],5500)
        self.assertEqual(len(f['expenses']),1)
        self.assertEqual(len(f['assets']),1)
        self.assertEqual(f['assets'][0]['net_cents'],15000)

    def test_month_boundaries_leap_and_no_future_leak(self):
        self.add(day='2026-01-31')
        self.add(day='2026-02-01')
        self.assertEqual(self.snapshot()['cash_cents'],10000)
        self.assertEqual(len(self.snapshot()['transactions']),1)
        self.add(day='2024-02-29',amount='1')
        self.assertEqual(self.api.finance_snapshot('2024-02')['cash_cents'],100)
        for month in ('2026-13','2026-1','bad',202601,'1800-01','2101-01'):
            self.assertFalse(self.api.finance_snapshot(month)['ok'])

    def test_opening_balances_support_debt_and_validate(self):
        self.assertTrue(self.api.save_finance_settings({'opening_cash':'-100,25','opening_invested':'0'})['ok'])
        self.assertEqual(self.snapshot()['cash_cents'],-10025)
        for payload in (None,{}, {'opening_cash':'0','opening_invested':'-1'}):
            self.assertFalse(self.api.save_finance_settings(payload)['ok'])

    def test_finance_never_calls_google(self):
        with patch.object(self.api._google,'request_sync') as sync:
            item=self.add()
            self.api.toggle_transaction(item)
            self.api.save_budget({'month':self.month,'category':'Outros','amount':'1'})
            self.api.save_finance_settings({'opening_cash':'0','opening_invested':'0'})
            self.api.export_finances(self.month)
            self.api.delete_finance('finance_transactions',item)
            sync.assert_not_called()

    def test_csv_filtered_bom_quotes_and_formula_neutralization(self):
        self.add('expense','12,34',title='=HYPERLINK("bad")',category='Lazer',notes='linha 1\nlinha 2; acentuação')
        self.add('income','100',title='Receita')
        result=self.api.export_finances(self.month,{'kind':'expense','query':'hyperlink'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['count'],1)
        contents=Path(result['path']).read_bytes()
        self.assertTrue(contents.startswith(b'\xef\xbb\xbf'))
        rows=list(csv.reader(io.StringIO(contents.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[1][1], '\'=HYPERLINK("bad")')
        self.assertEqual(rows[1][3],'12,34')
        self.assertEqual(rows[1][-1],'linha 1\nlinha 2; acentuação')

    def test_backup_includes_finances_and_closes_destination(self):
        self.add()
        self.api.save_budget({'month':self.month,'category':'Outros','amount':'500'})
        self.api.save_finance_settings({'opening_cash':'100','opening_invested':'200'})
        result=self.api.backup()
        self.assertTrue(result['ok'])
        copied=Api(result['path']).finance_snapshot(self.month)
        self.assertEqual(copied['cash_cents'],20000)
        self.assertEqual(len(copied['budgets']),1)
        target=Path(result['path'])
        target.rename(target.with_suffix('.moved.db'))  # Windows recusa se a conexão ficar aberta.

    def test_upgrade_legacy_db_preserves_data_and_makes_one_backup(self):
        legacy=Path(self.temp.name)/'legacy.db'
        conn=sqlite3.connect(legacy)
        conn.executescript("CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT,project_id INTEGER,due TEXT DEFAULT '',priority TEXT DEFAULT 'Média',status TEXT DEFAULT 'A fazer',notes TEXT DEFAULT ''); INSERT INTO tasks(title) VALUES ('Antiga');")
        conn.close()
        upgraded=Api(legacy)
        self.assertEqual(upgraded.snapshot()['tasks'][0]['title'],'Antiga')
        self.assertEqual(upgraded.finance_snapshot(self.month)['transactions'],[])
        backups=list((legacy.parent/'backups').glob('antes-financas-*.db'))
        self.assertEqual(len(backups),1)
        conn=sqlite3.connect(backups[0])
        self.assertEqual(conn.execute('SELECT title FROM tasks').fetchone()[0],'Antiga')
        self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='finance_transactions'").fetchone())
        conn.close()
        Api(legacy)
        self.assertEqual(len(list((legacy.parent/'backups').glob('antes-financas-*.db'))),1)

    def test_concurrent_saves_are_not_lost(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda n:self.api.save_transaction(dict(title=str(n),kind='income',amount='0,10',day='2026-01-01',category='Outros')), range(20)))
        self.assertTrue(all(r['ok'] for r in results))
        self.assertEqual(self.snapshot()['cash_cents'],200)


if __name__ == '__main__':
    unittest.main()
