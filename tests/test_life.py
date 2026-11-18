import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from holy_planner.backend import Api
from holy_planner.database import Database
from holy_planner import finance_import
from holy_planner import life
TODAY = date.today()


class LifeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.api = Api(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def ok(self, result):
        self.assertTrue(result.get('ok', True), result)
        return result

    def workout(self, day=TODAY):
        return self.ok(self.api.save_workout(dict(title='Treino A', day=day.isoformat(),
            exercises=[dict(name='Supino', sets=[dict(weight=60, reps=10), dict(weight=60, reps=8)])])))['id']

    def sql(self, query, args=()):
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(query, args).fetchall()
        conn.close()
        return rows

    # ------------------------------------------------------------ ligações entre áreas
    def test_goals_follow_workouts_focus_routines_and_wealth(self):
        routine = self.ok(self.api.save('routines', dict(title='Ler', days=list(range(7)))))['id']
        self.ok(self.api.toggle_routine(routine, TODAY.isoformat()))
        self.workout()
        self.ok(self.api.save_focus_session(dict(id='focus-session-01', title='Estudo', minutes=25, day=TODAY.isoformat())))
        self.ok(self.api.save_wealth_record(dict(day=TODAY.isoformat(), amount='12.345,67')))
        for title, source, extra in [('Treinos', 'workouts', {}), ('Foco', 'focus', {}), ('Leitura', 'routine', {'source_ref': routine}),
                                     ('Carteira', 'wealth', {})]:
            self.ok(self.api.save_productivity('goals', dict(title=title, target=100000, current=999, unit='u', source=source, period='week', **extra)))
        goals = {g['title']: g for g in self.api.productivity_snapshot()['goals']}
        self.assertEqual({k: goals[k]['current'] for k in goals}, {'Treinos': 1, 'Foco': 25, 'Leitura': 1, 'Carteira': 12345})
        self.assertTrue(all(g['auto'] for g in goals.values()))
        self.assertFalse(self.api.save_productivity('goals', dict(title='X', target=1, unit='u', source='routine'))['ok'])
        self.assertFalse(self.api.save_productivity('goals', dict(title='X', target=1, unit='u', source='nope'))['ok'])

    def test_workout_checks_linked_routine_and_task_creates_bill(self):
        linked = self.ok(self.api.save('routines', dict(title='Academia', days=list(range(7)), auto_workout='1')))['id']
        other = self.ok(self.api.save('routines', dict(title='Água', days=list(range(7)))))['id']
        self.workout()
        done = {r['id']: r['done'] for r in self.api.snapshot()['routines']}
        self.assertEqual((done[linked], done[other]), (True, False))
        due = (TODAY + timedelta(days=3)).isoformat()
        result = self.ok(self.api.save('tasks', dict(title='Pagar IPVA', due=due, finance_amount='1.234,56', finance_category='')))
        self.assertEqual(result['warning'], '')
        self.assertEqual(self.sql("SELECT title,kind,amount_cents,day,status FROM finance_transactions"), [('Pagar IPVA', 'expense', 123456, due, 'pending')])
        self.assertFalse(self.api.save('tasks', dict(title='Sem prazo', finance_amount='10'))['ok'])

    def test_completed_at_is_tracked_for_every_status_change(self):
        task = self.ok(self.api.save('tasks', dict(title='T')))['id']
        self.ok(self.api.toggle_task(task))
        self.assertTrue(self.sql('SELECT completed_at FROM tasks WHERE id=?', (task,))[0][0].startswith(TODAY.isoformat()))
        self.ok(self.api.set_task_status(task, 'Em andamento'))
        self.assertEqual(self.sql('SELECT completed_at FROM tasks WHERE id=?', (task,))[0][0], '')

    # ------------------------------------------------------------ lembretes e configurações
    def test_reminders_respect_hour_and_settings(self):
        self.ok(self.api.save('routines', dict(title='Meditar', days=list(range(7)))))
        self.ok(self.api.save('tasks', dict(title='Hoje', due=TODAY.isoformat())))
        tomorrow = (TODAY + timedelta(days=1)).isoformat()
        self.ok(self.api.save_transaction(dict(title='Luz', kind='expense', amount='180', day=tomorrow, category='Moradia', status='pending')))
        morning = datetime.combine(TODAY, datetime.min.time()).replace(hour=8)
        kinds = {i['kind'] for i in self.ok(self.api.reminders(morning))['items']}
        self.assertIn('tasks', kinds)
        self.assertIn('finance', kinds)
        self.assertNotIn('routines', kinds)
        night = morning.replace(hour=21)
        night_items = self.ok(self.api.reminders(night))['items']
        self.assertIn('routines', {i['kind'] for i in night_items})
        self.assertIn('journal', {i['kind'] for i in night_items})
        self.assertEqual(len({i['key'] for i in night_items}), len(night_items))
        self.ok(self.api.save_app_settings(dict(reminder_hour=22)))
        self.assertNotIn('routines', {i['kind'] for i in self.ok(self.api.reminders(night))['items']})
        self.ok(self.api.save_app_settings(dict(reminders_enabled=False)))
        self.assertEqual(self.ok(self.api.reminders(night))['items'], [])
        self.assertFalse(self.api.save_app_settings(dict(reminder_hour=24))['ok'])
        self.assertFalse(self.api.save_app_settings(dict(reminders_enabled='sim'))['ok'])
        settings = self.ok(self.api.app_settings())
        self.assertEqual((settings['reminders_enabled'], settings['reminder_hour']), (False, 22))

    def test_notification_and_autostart_are_local_only(self):
        calls = []
        self.api._toast_runner = lambda command, **kwargs: calls.append((command, kwargs['env']))
        self.ok(self.api.notify('Rotinas', 'Faltam 2 <rotinas>'))
        self.assertEqual(calls[0][1]['HP_BODY'], 'Faltam 2 <rotinas>')
        self.assertNotIn('<rotinas>', ' '.join(calls[0][0]))  # texto vai por variável de ambiente, não no comando
        with mock.patch.dict(os.environ, {'APPDATA': self.temp.name}):
            self.ok(self.api.set_autostart(True))
            target = life.startup_file()
            self.assertTrue(target.exists())
            self.assertIn('start ""', target.read_text(encoding='utf-8'))
            self.ok(self.api.set_autostart(False))
            self.assertFalse(target.exists())
        from holy_planner import web_app
        self.assertNotIn('notify', web_app.METHODS)
        self.assertNotIn('set_autostart', web_app.METHODS)
        for method in ('reminders', 'review_snapshot', 'save_journal', 'import_preview', 'import_commit', 'delete_transaction', 'save_workout_template'):
            self.assertIn(method, web_app.METHODS)

    # ------------------------------------------------------------ revisão semanal
    def test_weekly_review_summary_save_and_planning(self):
        first = life.monday(TODAY)
        task = self.ok(self.api.save('tasks', dict(title='Feita')))['id']
        self.ok(self.api.toggle_task(task))
        undated = self.ok(self.api.save('tasks', dict(title='Sem data', priority='Alta')))['id']
        self.workout()
        self.ok(self.api.save_journal(dict(day=TODAY.isoformat(), mood=4, energy=3, sleep='7,5')))
        snap = self.ok(self.api.review_snapshot(first.isoformat()))
        self.assertEqual([t['title'] for t in snap['tasks_done']], ['Feita'])
        self.assertEqual(snap['workouts'], 1)
        self.assertEqual(snap['journal']['mood'], 4)
        self.assertEqual(snap['journal']['sleep'], 7.5)
        self.assertIn(undated, [t['id'] for t in snap['undated']])
        self.ok(self.api.save_review(dict(week=first.isoformat(), wins='Treinei', lessons='Dormir cedo', priorities=['A', ' ', 'C'])))
        self.assertEqual(self.ok(self.api.review_snapshot(first.isoformat()))['review']['priorities'], ['A', 'C'])
        self.assertFalse(self.api.save_review(dict(week=(first + timedelta(days=1)).isoformat()))['ok'])
        self.assertFalse(self.api.save_review(dict(week=first.isoformat(), priorities=['1', '2', '3', '4']))['ok'])
        next_day = (first + timedelta(days=8)).isoformat()
        self.ok(self.api.schedule_tasks([dict(id=undated, due=next_day)]))
        self.assertEqual(self.sql('SELECT due FROM tasks WHERE id=?', (undated,))[0][0], next_day)
        self.assertFalse(self.api.schedule_tasks([dict(id=9999, due=next_day)])['ok'])
        self.assertEqual(life.review_week_for(first + timedelta(days=6)), first.isoformat())
        self.assertEqual(life.review_week_for(first + timedelta(days=7)), first.isoformat())
        self.assertIsNone(life.review_week_for(first + timedelta(days=2)))

    # ------------------------------------------------------------ diário
    def test_journal_merges_fields_and_finds_patterns(self):
        self.ok(self.api.save_journal(dict(day=TODAY.isoformat(), mood=5)))
        self.ok(self.api.save_journal(dict(day=TODAY.isoformat(), sleep='8', note='Bom dia')))
        entry = self.ok(self.api.journal_snapshot())['entry']
        self.assertEqual((entry['mood'], entry['sleep'], entry['note']), (5, 8.0, 'Bom dia'))
        for bad in (dict(mood=6), dict(sleep='25'), dict(sleep='abc'), dict(energy=True)):
            self.assertFalse(self.api.save_journal(dict(day=TODAY.isoformat(), **bad))['ok'], bad)
        self.assertFalse(self.api.save_journal(dict(day=(TODAY + timedelta(days=1)).isoformat(), mood=3))['ok'])
        for offset in range(1, 9):
            day = TODAY - timedelta(days=offset)
            trained = offset % 2 == 0
            if trained:
                self.workout(day)
            self.ok(self.api.save_journal(dict(day=day.isoformat(), mood=5 if trained else 2, energy=4, sleep='8' if trained else '6')))
        insights = {i['key']: i for i in self.ok(self.api.journal_snapshot())['insights']}
        self.assertGreater(insights['mood_workout']['a_value'], insights['mood_workout']['b_value'])
        self.ok(self.api.delete_journal(TODAY.isoformat()))
        self.assertIsNone(self.ok(self.api.journal_snapshot())['entry'])

    # ------------------------------------------------------------ finanças
    def test_series_edit_and_delete_from_this_one_onwards(self):
        start = TODAY.replace(day=1)
        self.ok(self.api.save_transaction(dict(title='Academia', kind='expense', amount='100', day=start.isoformat(),
                                               category='Saúde', status='paid', repeat_months='4')))
        ids = [r[0] for r in self.sql('SELECT id FROM finance_transactions ORDER BY day')]
        self.assertEqual(len({r[0] for r in self.sql('SELECT series FROM finance_transactions')}), 1)
        second = self.sql('SELECT * FROM finance_transactions WHERE id=?', (ids[1],))
        payload = dict(title='Academia nova', kind='expense', amount='120', day=second[0][4], category='Saúde', status='pending', scope='future')
        self.assertEqual(self.ok(self.api.save_transaction(payload, ids[1]))['count'], 3)
        self.assertEqual([r[0] for r in self.sql('SELECT amount_cents FROM finance_transactions ORDER BY day')], [10000, 12000, 12000, 12000])
        self.assertEqual(self.ok(self.api.delete_transaction(ids[2], 'future'))['count'], 2)
        self.assertEqual(len(self.sql('SELECT id FROM finance_transactions')), 2)
        self.assertFalse(self.api.save_transaction({**payload, 'scope': 'all'}, ids[1])['ok'])

    def test_copy_budgets_and_daily_allowance(self):
        month = TODAY.strftime('%Y-%m')
        previous = (TODAY.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
        self.ok(self.api.save_budget(dict(month=previous, category='Lazer', amount='300')))
        self.ok(self.api.save_budget(dict(month=previous, category='Alimentação', amount='900')))
        self.ok(self.api.save_budget(dict(month=month, category='Lazer', amount='500')))
        self.assertEqual(self.ok(self.api.copy_budgets(month))['count'], 1)
        budgets = {b['category']: b['amount_cents'] for b in self.api.finance_snapshot(month)['budgets']}
        self.assertEqual(budgets, {'Lazer': 50000, 'Alimentação': 90000})
        self.ok(self.api.save_finance_settings(dict(opening_cash='3000', opening_invested='0')))
        snap = self.api.finance_snapshot(month)
        self.assertEqual(snap['daily_allowance_cents'], 300000 // snap['days_left'])
        self.assertEqual(self.api.snapshot()['money_today']['allowance_cents'], snap['daily_allowance_cents'])

    def test_import_csv_and_ofx_with_categories_and_duplicates(self):
        self.ok(self.api.save_transaction(dict(title='Padaria do Zé', kind='expense', amount='20', day='2026-01-05', category='Lazer', status='paid')))
        csv_text = 'Data;Descrição;Valor\n05/01/2026;Padaria do Zé;-20,00\n06/01/2026;UBER *TRIP;-32,50\n07/01/2026;Salário ACME;5.000,00\n'
        preview = self.ok(self.api.import_preview(csv_text, 'extrato.csv', False))
        rows = {r['title']: r for r in preview['rows']}
        self.assertTrue(rows['Padaria do Zé']['duplicate'])
        self.assertEqual(rows['Padaria do Zé']['category'], 'Lazer')  # aprende com o histórico
        self.assertEqual((rows['UBER *TRIP']['kind'], rows['UBER *TRIP']['category'], rows['UBER *TRIP']['amount_cents']), ('expense', 'Transporte', 3250))
        self.assertEqual((rows['Salário ACME']['kind'], rows['Salário ACME']['category']), ('income', 'Salário'))
        chosen = [r for r in preview['rows'] if not r['duplicate']]
        self.assertEqual(self.ok(self.api.import_commit(chosen, 'Nubank'))['count'], 2)
        self.assertEqual(self.ok(self.api.import_commit(chosen, 'Nubank'))['count'], 0)  # reimportar não duplica
        ofx = ('OFXHEADER:100\n<OFX><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260110120000[-3:BRT]<TRNAMT>-89.90'
               '<FITID>abc1<MEMO>NETFLIX.COM</STMTTRN><STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260111<TRNAMT>150.00<FITID>abc2<MEMO>PIX RECEBIDO</STMTTRN></BANKTRANLIST></OFX>')
        rows = self.ok(self.api.import_preview(ofx, 'banco.ofx', False))['rows']
        self.assertEqual([(r['day'], r['kind'], r['amount_cents'], r['category']) for r in rows],
                         [('2026-01-11', 'income', 15000, 'Outros'), ('2026-01-10', 'expense', 8990, 'Assinaturas')])
        card = self.ok(self.api.import_preview('date,title,amount\n2026-01-12,Mercado Bom,45.10\n', 'fatura.csv', True))['rows'][0]
        self.assertEqual((card['kind'], card['category']), ('expense', 'Alimentação'))
        self.assertFalse(self.api.import_preview('nada aqui', 'x.csv', False)['ok'])
        self.assertFalse(self.api.import_commit([dict(key='x', day='2026-01-01')], '')['ok'])

    def test_amount_and_date_parsing(self):
        self.assertEqual([finance_import.parse_amount(v) for v in ('1.234,56', '-1.234,56', '1,234.56', 'R$ 10,00', '(5,00)', '7,5-')],
                         [123456, -123456, 123456, 1000, -500, -750])
        self.assertEqual(finance_import.parse_date('05/02/26'), date(2026, 2, 5))
        self.assertIsNone(finance_import.parse_date('31/02/2026'))

    # ------------------------------------------------------------ treinos
    def test_workout_templates_and_last_values(self):
        self.workout(TODAY - timedelta(days=3))
        self.ok(self.api.save_workout(dict(title='Leve', day=TODAY.isoformat(), exercises=[dict(name='Rosca', sets=[dict(weight=12, reps=10)])])))
        template = self.ok(self.api.save_workout_template(dict(name='Treino A', exercises=[dict(name='Supino', sets=3)], cardio=[dict(name='Esteira', minutes=15)])))['id']
        snap = self.api.workouts_snapshot()
        self.assertEqual(snap['templates'][0]['exercises'], [{'name': 'Supino', 'sets': 3}])
        self.assertEqual(snap['last_exercises']['supino']['suggested'], 62.5)
        self.assertEqual(snap['last_exercises']['rosca']['suggested'], 13)
        self.assertFalse(self.api.save_workout_template(dict(name='Vazia'))['ok'])
        self.ok(self.api.delete_workout_template(template))
        self.assertEqual(self.api.workouts_snapshot()['templates'], [])

    def test_migration_backup_for_version_5(self):
        legacy = Path(self.temp.name) / 'legacy.db'
        with sqlite3.connect(self.path) as source, sqlite3.connect(legacy) as target:
            source.backup(target)
        with sqlite3.connect(legacy) as conn:
            conn.execute('DROP TABLE journal')
        conn.close()
        Database(legacy).conn.close()
        self.assertTrue(any(p.name.startswith('antes-5.0-') for p in (legacy.parent / 'backups').iterdir()))


if __name__ == '__main__':
    unittest.main()
