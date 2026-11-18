import copy
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from holy_planner.backend import Api


class WorkoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'planner.db'
        self.api = Api(self.path)
        self.payload = dict(title='Treino A', day=date.today().isoformat(), notes='Bom treino',
            exercises=[dict(name='Supino reto', notes='Carga total', sets=[dict(weight='20,25', reps='12'), dict(weight=25, reps=10)])],
            cardio=[dict(name='Corrida', minutes=30, distance_km=5, notes='Esteira')])

    def tearDown(self):
        self.temp.cleanup()

    def save(self, payload=None, item_id=None):
        result = self.api.save_workout(payload if payload is not None else self.payload, item_id)
        self.assertTrue(result['ok'], result)
        return result['id']

    def test_roundtrip_metrics_backup_and_cascade(self):
        item = self.save()
        snap = self.api.workouts_snapshot()
        row = snap['sessions'][0]
        self.assertEqual(row['metrics'], dict(sets=2,reps=22,volume=493,cardio_minutes=30,distance_km=5))
        self.assertEqual(row['exercises'][0]['notes'], 'Carga total')
        self.assertEqual(snap['cardio'][0]['points'][0]['pace'], 6)
        restored = Api(self.api.backup()['path'])
        self.assertEqual(restored.workouts_snapshot(), snap)
        self.assertTrue(self.api.delete_workout(item)['ok'])
        with sqlite3.connect(self.path) as conn:
            for table in ('workout_sessions','workout_exercises','workout_sets','workout_cardio'):
                self.assertEqual(conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0], 0)
        conn.close()

    def test_edit_revision_and_retry_prevent_overwrite_or_duplicate(self):
        payload = {**self.payload, 'client_id':'test-retry-token'}
        item = self.save(payload)
        self.assertEqual(self.save(payload), item)
        self.assertEqual(len(self.api.workouts_snapshot()['sessions']), 1)
        old = self.api.workouts_snapshot()['sessions'][0]
        changed = copy.deepcopy(old)
        changed['exercises'][0]['sets'][0]['weight'] = 30
        changed['cardio'] = []
        self.save(changed, item)
        self.assertFalse(self.api.save_workout(old, item)['ok'])
        result = self.api.workouts_snapshot()['sessions'][0]
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['metrics']['volume'], 610)
        self.assertEqual(result['cardio'], [])
        self.assertFalse(self.api.save_workout(changed, 999)['ok'])

    def test_validation_does_not_change_existing_workout(self):
        item = self.save()
        original = self.api.workouts_snapshot()
        invalid = [dict(title=''),dict(day='2026-02-31'),dict(day=(date.today()+timedelta(days=1)).isoformat()),
                   dict(exercises=[],cardio=[]),dict(exercises='invalid'),dict(exercises=[dict(name='X',sets=[])]),
                   dict(cardio=[dict(name='X',minutes=0)]),dict(cardio=[dict(name='X',minutes=1,distance_km=0)])]
        for weight in (-1,True,'NaN','Infinity','0.001',2001):
            invalid.append(dict(exercises=[dict(name='X',sets=[dict(weight=weight,reps=10)])]))
        for reps in (0,True,1.5,1001):
            invalid.append(dict(exercises=[dict(name='X',sets=[dict(weight=1,reps=reps)])]))
        for change in invalid:
            with self.subTest(change=change):
                self.assertFalse(self.api.save_workout({**self.payload, 'revision':1, **change}, item)['ok'])
                self.assertEqual(self.api.workouts_snapshot(), original)

    def test_bodyweight_and_cardio_without_distance(self):
        self.save(dict(title='Movimento', day=date.today().isoformat(),
            exercises=[dict(name='Flexão', sets=[dict(weight=0,reps=15)])],
            cardio=[dict(name='Escada',minutes='10,5',distance_km='')]))
        snap = self.api.workouts_snapshot()
        self.assertEqual(snap['strength'][0]['points'][0]['reps'], 15)
        self.assertEqual(snap['strength'][0]['points'][0]['volume'], 0)
        self.assertIsNone(snap['cardio'][0]['points'][0]['pace'])
        self.assertIsNone(snap['cardio'][0]['points'][0]['distance_km'])
        self.assertEqual(snap['summary']['cardio_minutes'], 10.5)

    def test_normalized_names_group_sets_but_keep_sessions_and_modalities_separate(self):
        first = copy.deepcopy(self.payload)
        first['day'] = (date.today()-timedelta(days=7)).isoformat()
        self.save(first)
        second = copy.deepcopy(self.payload)
        second['exercises'] = [dict(name='  SUPINO   reto ',sets=[dict(weight=30,reps=8)]),dict(name='supino reto',sets=[dict(weight=20,reps=15)])]
        second['cardio'].extend([dict(name=' corrida ',minutes=15,distance_km=2),dict(name='Bicicleta',minutes=20)])
        self.save(second)
        self.save(second)
        snap=self.api.workouts_snapshot()
        self.assertEqual(snap['summary']['days'],2)
        self.assertEqual(len(snap['strength']),1)
        points=snap['strength'][0]['points']
        self.assertEqual(len(points),3)
        self.assertEqual([p['volume'] for p in points],[493,540,540])
        self.assertEqual(points[-1]['max_weight'],30)
        cardio={c['key']:c['points'] for c in snap['cardio']}
        self.assertAlmostEqual(cardio['corrida'][-1]['pace'],45/7,places=4)
        self.assertIsNone(cardio['bicicleta'][-1]['pace'])
        filtered=self.api.workouts_snapshot(date.today().isoformat(),date.today().isoformat())
        self.assertEqual(filtered['summary']['sessions'],2)
        self.assertEqual(len(filtered['strength'][0]['points']),2)
        self.assertFalse(self.api.workouts_snapshot(date.today().isoformat(),first['day'])['ok'])

    def test_partial_distance_does_not_produce_misleading_pace(self):
        self.save({**self.payload,'cardio':[dict(name='Corrida',minutes=10,distance_km=2),dict(name='Corrida',minutes=20)]})
        point=self.api.workouts_snapshot()['cardio'][0]['points'][0]
        self.assertEqual(point['minutes'],30)
        self.assertIsNone(point['distance_km'])
        self.assertIsNone(point['pace'])

    def test_storage_failure_rolls_back_parent_and_children(self):
        item=self.save()
        original=self.api.workouts_snapshot()
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TRIGGER fail_set BEFORE INSERT ON workout_sets BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        conn.close()
        self.assertFalse(self.api.save_workout({**self.payload,'revision':1,'title':'Changed'},item)['ok'])
        self.assertFalse(self.api.save_workout(self.payload)['ok'])
        self.assertEqual(self.api.workouts_snapshot(),original)

    def test_migration_backs_up_old_data_once(self):
        self.api.save('tasks',dict(title='Preservar'))
        with sqlite3.connect(self.path) as conn:
            for table in ('workout_sets','workout_exercises','workout_cardio','workout_sessions'):
                conn.execute(f'DROP TABLE {table}')
        conn.close()
        reopened=Api(self.path)
        self.assertEqual(reopened.snapshot()['tasks'][0]['title'],'Preservar')
        self.assertEqual(reopened.workouts_snapshot()['sessions'],[])
        backups=list(self.path.parent.glob('backups/antes-treinos-*.db'))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as conn:
            self.assertEqual(conn.execute('SELECT title FROM tasks').fetchone()[0],'Preservar')
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='workout_sessions'").fetchone())
        conn.close()
        Api(self.path)
        self.assertEqual(len(list(self.path.parent.glob('backups/antes-treinos-*.db'))),1)
