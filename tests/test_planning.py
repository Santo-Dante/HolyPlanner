import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from holy_planner.backend import Api
from holy_planner.database import Database


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.api = Api(self.path)
        self.scenario = {'name': 'Moderado', 'start_mode': 'snapshot', 'monthly': '1.000,00', 'annual_rate': '10,5',
                         'inflation': '4', 'raise': '3', 'years': 10, 'target': '250000', 'notes': 'Teste',
                         'events': [dict(title='13º', kind='deposit', month='2030-12', amount='3000', yearly=True),
                                     dict(title='Carro', kind='withdrawal', month='2031-05', amount='40.000,00')]}

    def tearDown(self):
        self.temp.cleanup()

    def test_scenario_roundtrip_edit_and_cascade(self):
        result = self.api.save_scenario(self.scenario)
        self.assertTrue(result['ok'], result)
        row = self.api.planning_snapshot()['scenarios'][0]
        self.assertEqual((row['monthly_cents'], row['annual_rate_bp'], row['inflation_bp'], row['raise_bp'], row['target_cents']),
                         (100000, 1050, 400, 300, 25000000))
        self.assertEqual([(e['title'], e['kind'], e['amount_cents'], e['yearly']) for e in row['events']],
                         [('13º', 'deposit', 300000, 1), ('Carro', 'withdrawal', 4000000, 0)])
        edited = {**self.scenario, 'name': 'Pessimista', 'annual_rate': '6', 'events': []}
        self.assertTrue(self.api.save_scenario(edited, result['id'])['ok'])
        row = self.api.planning_snapshot()['scenarios'][0]
        self.assertEqual((row['name'], row['annual_rate_bp'], row['events']), ('Pessimista', 600, []))
        self.assertTrue(self.api.set_scenario_visible(result['id'], False)['ok'])
        self.assertEqual(self.api.planning_snapshot()['scenarios'][0]['visible'], 0)
        self.assertTrue(self.api.save_scenario(self.scenario, result['id'])['ok'])
        self.assertTrue(self.api.delete_planning('investment_scenarios', result['id'])['ok'])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM investment_scenario_events').fetchone()[0], 0)
        conn.close()

    def test_invalid_scenarios_are_rejected_without_changes(self):
        for change in ({'years': 0}, {'years': 61}, {'annual_rate': '10,555'}, {'annual_rate': '500'},
                       {'monthly': '-5'}, {'name': ''}, {'start_mode': 'x'},
                       {'events': [dict(title='X', kind='deposit', month='2030-13', amount='1')]},
                       {'events': [dict(title='X', kind='gift', month='2030-01', amount='1')]},
                       {'events': [dict(title='X', kind='deposit', month='2030-01', amount='0')]}):
            result = self.api.save_scenario({**self.scenario, **change})
            self.assertFalse(result['ok'], change)
        self.assertEqual(self.api.planning_snapshot()['scenarios'], [])

    def test_wealth_records_upsert_and_history(self):
        today = date.today()
        old = (today.replace(day=1) - timedelta(days=40)).replace(day=15)
        self.assertTrue(self.api.save_finance_settings(dict(opening_cash='0', opening_invested='1000'))['ok'])
        self.assertTrue(self.api.save_transaction(dict(title='Aporte', kind='investment', amount='500', day=old.isoformat(),
                        category='Investimentos', asset='CDB', status='paid'))['ok'])
        self.assertTrue(self.api.save_wealth_record(dict(day=old.isoformat(), amount='1.600,00'))['ok'])
        self.assertTrue(self.api.save_wealth_record(dict(day=old.isoformat(), amount='1.650,00', notes='corrigido'))['ok'])
        self.assertFalse(self.api.save_wealth_record(dict(day=(today + timedelta(days=1)).isoformat(), amount='1'))['ok'])
        snap = self.api.planning_snapshot()
        self.assertEqual(len(snap['snapshots']), 1)
        self.assertEqual((snap['latest_snapshot']['amount_cents'], snap['latest_snapshot']['notes']), (165000, 'corrigido'))
        self.assertEqual(snap['capital_cents'], 150000)
        self.assertEqual(snap['series'][0]['month'], old.isoformat()[:7])
        self.assertEqual(snap['series'][-1]['capital_cents'], 150000)
        self.assertEqual(snap['series'][-1]['month'], today.isoformat()[:7])
        record = snap['snapshots'][0]['id']
        self.assertTrue(self.api.delete_planning('investment_snapshots', record)['ok'])
        self.assertIsNone(self.api.planning_snapshot()['latest_snapshot'])

    def test_backup_and_migration_from_previous_version(self):
        self.assertTrue(self.api.save_scenario(self.scenario)['ok'])
        restored = Api(self.api.backup()['path'])
        self.assertEqual(restored.planning_snapshot()['scenarios'], self.api.planning_snapshot()['scenarios'])
        legacy = Path(self.temp.name) / 'legacy.db'
        with sqlite3.connect(self.path) as source, sqlite3.connect(legacy) as target:
            source.backup(target)
        with sqlite3.connect(legacy) as conn:
            for table in ('investment_scenario_events', 'investment_scenarios', 'investment_snapshots'):
                conn.execute(f'DROP TABLE {table}')
        conn.close()
        Database(legacy).conn.close()
        self.assertTrue(any(p.name.startswith('antes-planejamento-') for p in (legacy.parent / 'backups').iterdir()))
        self.assertTrue(Api(legacy).save_scenario(self.scenario)['ok'])

    def test_monthly_repeat_creates_future_pending_copies(self):
        start = date.today().replace(day=1)
        payload = dict(title='Aluguel', kind='expense', amount='1500', day=start.isoformat(), category='Moradia',
                       status='paid', repeat_months='3')
        result = self.api.save_transaction(payload)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['count'], 3)
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute('SELECT day,status FROM finance_transactions ORDER BY day').fetchall()
        conn.close()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], (start.isoformat(), 'paid'))
        self.assertTrue(all(status == 'pending' for _, status in rows[1:]))
        end_of_month = dict(payload, day='2027-01-31', status='pending', repeat_months='2')
        self.assertTrue(self.api.save_transaction(end_of_month)['ok'])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT day FROM finance_transactions WHERE day LIKE '2027-02%'").fetchone()[0], '2027-02-28')
        conn.close()
        self.assertFalse(self.api.save_transaction(dict(payload, repeat_months='61'))['ok'])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM finance_transactions').fetchone()[0], 5)
        conn.close()

    def test_web_server_exposes_planning_methods(self):
        from holy_planner import web_app
        for method in ('planning_snapshot', 'save_wealth_record', 'save_scenario', 'set_scenario_visible', 'delete_planning'):
            self.assertIn(method, web_app.METHODS)


if __name__ == '__main__':
    unittest.main()
