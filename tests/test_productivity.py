import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from holy_planner.backend import Api


class ProductivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.api = Api(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_goals_and_notes_persist_and_backup(self):
        goal = self.api.save_productivity('goals', dict(title='Ler', target='12', current='3', unit='livros'))
        self.assertTrue(goal['ok'])
        note = self.api.save_productivity('notes', dict(title='Ideias', body='<script>texto</script>', pinned='1'))
        self.assertTrue(note['ok'])
        copy = Api(self.api.backup()['path'])
        self.assertEqual(copy.productivity_snapshot()['goals'][0]['current'], 3)
        self.assertEqual(copy.productivity_snapshot()['notes'][0]['body'], '<script>texto</script>')
        self.assertTrue(self.api.delete_productivity('notes', note['id'])['ok'])
        self.assertEqual(self.api.productivity_snapshot()['notes'], [])

    def test_validation_rejects_bad_values_without_writes(self):
        for payload in [dict(title='X',target=0,unit='x'), dict(title='X',target=1.2,unit='x'),
                        dict(title='X',target=True,unit='x'), dict(title=' ',target=1,unit='x'),
                        dict(title='X',target=1,current=-1,unit='x'), dict(title='X',target=1,unit='x',due='2026-02-31')]:
            self.assertFalse(self.api.save_productivity('goals',payload)['ok'])
        self.assertFalse(self.api.save_productivity('tasks', {'title':'X'})['ok'])
        self.assertFalse(self.api.delete_productivity('goals; DROP TABLE tasks',1)['ok'])
        self.assertFalse(self.api.save_productivity('notes', {'title':'X'},999)['ok'])
        self.assertEqual(self.api.productivity_snapshot()['goals'], [])

    def test_focus_is_idempotent_and_survives_task_deletion(self):
        task = self.api.save('tasks', {'title':'Estudar'})['id']
        payload = dict(id='session-test-001', task_id=task, title='Estudar', minutes=25,day=date.today().isoformat())
        self.assertTrue(self.api.save_focus_session(payload)['ok'])
        self.assertTrue(self.api.save_focus_session(payload)['ok'])
        self.api.delete('tasks',task)
        result = self.api.productivity_snapshot()
        self.assertEqual(result['focus_today'], 25)
        self.assertEqual(result['focus_week'], 25)
        self.assertEqual(len(result['sessions']), 1)
        self.assertIsNone(result['sessions'][0]['task_id'])
        self.assertTrue(self.api.save_focus_session({**payload,'id':'session-test-002'})['ok'])
        self.assertEqual(self.api.productivity_snapshot()['focus_today'],50)

    def test_focus_rejects_future_and_invalid_duration(self):
        payload=dict(id='session-invalid',minutes=25,day=date.today().isoformat())
        for value in (0,181,-1,1.5,True):
            self.assertFalse(self.api.save_focus_session({**payload,'minutes':value})['ok'])
        self.assertFalse(self.api.save_focus_session({**payload,'day':(date.today()+timedelta(days=1)).isoformat()})['ok'])
        self.assertEqual(self.api.productivity_snapshot()['focus_today'],0)

    def test_task_planning_and_status_preserve_details(self):
        task = self.api.save('tasks',dict(title='Ler',estimate_minutes='40',scheduled_time='09:30',priority='Alta',notes='Capítulo 2'))['id']
        self.assertTrue(self.api.set_task_status(task,'Em andamento')['ok'])
        self.assertFalse(self.api.set_task_status(task,'Invalid')['ok'])
        row = self.api.snapshot()['tasks'][0]
        self.assertEqual((row['estimate_minutes'],row['scheduled_time'],row['notes']),(40,'09:30','Capítulo 2'))
        self.assertEqual(row['status'],'Em andamento')
        # Existing clients that omit new fields do not erase them.
        self.api.save('tasks',dict(title='Ler mais'),task)
        self.assertEqual(self.api.snapshot()['tasks'][0]['scheduled_time'],'09:30')
        for value in ('24:00','9:00','12:99','hello'):
            self.assertFalse(self.api.save('tasks',dict(title='X',scheduled_time=value))['ok'])

    def test_legacy_database_migration_keeps_task_and_finances(self):
        self.api.save('tasks',dict(title='Original'))
        self.api.save_finance_settings(dict(opening_cash='1234.56',opening_invested='0'))
        with sqlite3.connect(self.path) as conn:
            conn.execute('DROP TABLE focus_sessions')
            conn.execute('DROP TABLE notes')
            conn.execute('DROP TABLE goals')
            conn.execute('ALTER TABLE tasks DROP COLUMN estimate_minutes')
            conn.execute('ALTER TABLE tasks DROP COLUMN scheduled_time')
        conn.close()
        reopened=Api(self.path)
        self.assertEqual(reopened.snapshot()['tasks'][0]['title'],'Original')
        self.assertEqual(reopened.snapshot()['tasks'][0]['estimate_minutes'],0)
        self.assertEqual(reopened.finance_snapshot()['settings']['opening_cash_cents'],123456)
        self.assertEqual(reopened.productivity_snapshot()['notes'],[])
