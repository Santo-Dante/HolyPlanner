"""Diário de treinos e métricas descritivas dos registros do usuário."""
import re
import sqlite3
import json
import uuid
from datetime import datetime
from datetime import date
from decimal import Decimal, InvalidOperation

from .productivity import bounded_integer


def initialize_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY, client_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, day TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
            revision INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_workouts_day ON workout_sessions(day);
        CREATE TABLE IF NOT EXISTS workout_exercises (
            id INTEGER PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, name TEXT NOT NULL, name_key TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_workout_exercises_session ON workout_exercises(session_id);
        CREATE TABLE IF NOT EXISTS workout_sets (
            id INTEGER PRIMARY KEY,
            exercise_id INTEGER NOT NULL REFERENCES workout_exercises(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, weight_hundredths INTEGER NOT NULL CHECK(weight_hundredths>=0),
            reps INTEGER NOT NULL CHECK(reps>0)
        );
        CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise ON workout_sets(exercise_id);
        CREATE TABLE IF NOT EXISTS workout_cardio (
            id INTEGER PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, name TEXT NOT NULL, name_key TEXT NOT NULL,
            seconds INTEGER NOT NULL CHECK(seconds>0), meters INTEGER,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_workout_cardio_session ON workout_cardio(session_id);
        CREATE TABLE IF NOT EXISTS workout_templates (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL
        );
    ''')


def text(payload, key, label, limit=200, required=False):
    value = payload.get(key, '')
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{label}: preencha até {limit} caracteres.')
    return value.strip()


def scaled(value, scale, limit, label, optional=False):
    if optional and value in ('', None):
        return None
    if isinstance(value, bool) or not re.fullmatch(r'\d+(?:[.,]\d+)?', str(value)):
        raise ValueError(f'{label}: informe um número válido, sem separador de milhares.')
    try:
        number = Decimal(str(value).replace(',', '.')) * scale
        if not number.is_finite() or number < 0 or number > limit * scale or number != number.to_integral_value():
            raise ValueError(f'{label}: valor ou precisão inválidos.')
        return int(number)
    except InvalidOperation as exc:
        raise ValueError(f'{label}: número inválido.') from exc


def name_key(value):
    return ' '.join(value.split()).casefold()


def validate_workout(payload):
    if not isinstance(payload, dict):
        raise ValueError('Treino inválido.')
    day = date.fromisoformat(text(payload, 'day', 'Data', 10, True))
    if day > date.today():
        raise ValueError('Registre apenas treinos realizados até hoje.')
    result = dict(title=text(payload, 'title', 'Nome do treino', required=True), day=day.isoformat(),
                  notes=text(payload, 'notes', 'Observações', 10000), exercises=[], cardio=[])
    for field, maximum in (('exercises', 30), ('cardio', 20)):
        rows = payload.get(field, [])
        if not isinstance(rows, list) or len(rows) > maximum or any(not isinstance(r, dict) for r in rows):
            raise ValueError(f'Lista de {field} inválida (máximo {maximum} itens).')
        for row in rows:
            name = ' '.join(text(row, 'name', 'Exercício ou modalidade', 120, True).split())
            entry = dict(name=name, name_key=name_key(name), notes=text(row, 'notes', 'Observações', 2000))
            if field == 'exercises':
                sets = row.get('sets', [])
                if not isinstance(sets, list) or not 1 <= len(sets) <= 50 or any(not isinstance(s, dict) for s in sets):
                    raise ValueError('Cada exercício deve ter de 1 a 50 séries.')
                entry['sets'] = [dict(weight_hundredths=scaled(s.get('weight'), 100, 2000, 'Carga (kg)'),
                                      reps=bounded_integer(s.get('reps'), 1, 1000, 'Repetições')) for s in sets]
            else:
                entry['seconds'] = scaled(row.get('minutes'), 60, 1440, 'Duração (min)')
                entry['meters'] = scaled(row.get('distance_km'), 1000, 1000, 'Distância (km)', optional=True)
                if entry['seconds'] <= 0 or entry['meters'] == 0:
                    raise ValueError('Informe duração e distância positivas; deixe a distância vazia quando não medida.')
            result[field].append(entry)
    if not result['exercises'] and not result['cardio']:
        raise ValueError('Adicione pelo menos um exercício ou uma atividade de cardio.')
    return result


def validate_template(payload):
    if not isinstance(payload, dict):
        raise ValueError('Ficha inválida.')
    name = ' '.join(text(payload, 'name', 'Nome da ficha', 120, True).split())
    exercises, cardio = payload.get('exercises', []), payload.get('cardio', [])
    if not isinstance(exercises, list) or not isinstance(cardio, list) or len(exercises) > 30 or len(cardio) > 20:
        raise ValueError('A ficha aceita até 30 exercícios e 20 atividades de cardio.')
    body = dict(exercises=[], cardio=[])
    for row in exercises:
        if not isinstance(row, dict):
            raise ValueError('Exercício inválido.')
        body['exercises'].append(dict(name=' '.join(text(row, 'name', 'Exercício', 120, True).split()),
                                      sets=bounded_integer(row.get('sets', 3), 1, 50, 'Séries')))
    for row in cardio:
        if not isinstance(row, dict):
            raise ValueError('Cardio inválido.')
        body['cardio'].append(dict(name=' '.join(text(row, 'name', 'Modalidade', 120, True).split()),
                                   minutes=bounded_integer(row.get('minutes', 20), 1, 1440, 'Duração')))
    if not body['exercises'] and not body['cardio']:
        raise ValueError('Inclua pelo menos um exercício ou cardio na ficha.')
    return name, body


def suggested_weight(weight):
    """Progressão simples: +2,5 kg a partir de 20 kg, +1 kg abaixo disso; peso corporal fica igual."""
    if weight <= 0:
        return 0
    return round(weight + (2.5 if weight >= 20 else 1), 2)


def session_metrics(session):
    sets = [s for e in session['exercises'] for s in e['sets']]
    return dict(sets=len(sets), reps=sum(s['reps'] for s in sets),
                volume=round(sum(Decimal(str(s['weight'])) * s['reps'] for s in sets), 2),
                cardio_minutes=round(sum(c['minutes'] for c in session['cardio']), 2),
                distance_km=round(sum(c['distance_km'] or 0 for c in session['cardio']), 3))


def trends(sessions):
    strength, cardio = {}, {}
    for session in sorted(sessions, key=lambda s: (s['day'], s['id'])):
        grouped, grouped_cardio = {}, {}
        for exercise in session['exercises']:
            key = name_key(exercise['name'])
            grouped.setdefault(key, []).extend(exercise['sets'])
            strength.setdefault(key, dict(key=key, name=exercise['name'], points=[]))
        for key, sets in grouped.items():
            strength[key]['points'].append(dict(day=session['day'], session_id=session['id'], title=session['title'],
                max_weight=max(s['weight'] for s in sets), reps=sum(s['reps'] for s in sets), sets=len(sets),
                volume=float(round(sum(Decimal(str(s['weight'])) * s['reps'] for s in sets), 2))))
        for activity in session['cardio']:
            key = name_key(activity['name'])
            grouped_cardio.setdefault(key, []).append(activity)
            cardio.setdefault(key, dict(key=key, name=activity['name'], points=[]))
        for key, activities in grouped_cardio.items():
            minutes = round(sum(a['minutes'] for a in activities), 2)
            km = round(sum(a['distance_km'] or 0 for a in activities), 3)
            measured = all(a['distance_km'] is not None for a in activities)
            cardio[key]['points'].append(dict(day=session['day'], session_id=session['id'], title=session['title'],
                minutes=minutes, distance_km=km if measured else None,
                pace=round(minutes/km, 4) if measured and km else None))
    return sorted(strength.values(), key=lambda e:e['key']), sorted(cardio.values(), key=lambda e:e['key'])


class WorkoutsApi:
    def save_workout(self, payload, item_id=None):
        try:
            values = validate_workout(payload)
            client_id = payload.get('client_id') or uuid.uuid4().hex
            if not isinstance(client_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', client_id):
                raise ValueError('Identificador do treino inválido.')
            with self._database() as db, db.conn:
                conn = db.conn
                if item_id is None:
                    existing = conn.execute('SELECT id FROM workout_sessions WHERE client_id=?', (client_id,)).fetchone()
                    if existing:
                        return {'ok': True, 'id': existing['id']}
                    item_id = conn.execute('INSERT INTO workout_sessions(client_id,title,day,notes) VALUES (?,?,?,?)',
                        (client_id, values['title'], values['day'], values['notes'])).lastrowid
                else:
                    item_id = self._id(item_id)
                    row = conn.execute('SELECT revision FROM workout_sessions WHERE id=?', (item_id,)).fetchone()
                    if not row:
                        raise ValueError('Treino não encontrado. Atualize a tela.')
                    revision = bounded_integer(payload.get('revision'), 1, 1000000000, 'Revisão')
                    cursor = conn.execute('UPDATE workout_sessions SET title=?,day=?,notes=?,revision=revision+1 WHERE id=? AND revision=?',
                        (values['title'], values['day'], values['notes'], item_id, revision))
                    if cursor.rowcount != 1:
                        raise ValueError('Este treino mudou em outra tela. Cancele e abra-o novamente antes de editar.')
                    conn.execute('DELETE FROM workout_exercises WHERE session_id=?', (item_id,))
                    conn.execute('DELETE FROM workout_cardio WHERE session_id=?', (item_id,))
                for position, e in enumerate(values['exercises']):
                    exercise_id = conn.execute('INSERT INTO workout_exercises(session_id,position,name,name_key,notes) VALUES (?,?,?,?,?)',
                        (item_id, position, e['name'], e['name_key'], e['notes'])).lastrowid
                    conn.executemany('INSERT INTO workout_sets(exercise_id,position,weight_hundredths,reps) VALUES (?,?,?,?)',
                        [(exercise_id, i, s['weight_hundredths'], s['reps']) for i,s in enumerate(e['sets'])])
                for position, c in enumerate(values['cardio']):
                    conn.execute('INSERT INTO workout_cardio(session_id,position,name,name_key,seconds,meters,notes) VALUES (?,?,?,?,?,?,?)',
                        (item_id, position, c['name'], c['name_key'], c['seconds'], c['meters'], c['notes']))
            if hasattr(self, '_auto_check_workout'):
                self._auto_check_workout(values['day'])
            return {'ok': True, 'id': item_id}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_workout(self, item_id):
        try:
            with self._database() as db, db.conn:
                cursor = db.conn.execute('DELETE FROM workout_sessions WHERE id=?', (self._id(item_id),))
                if not cursor.rowcount:
                    raise ValueError('Treino não encontrado.')
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def workouts_snapshot(self, start='', end=''):
        try:
            start = date.fromisoformat(start).isoformat() if start else '0001-01-01'
            end = date.fromisoformat(end).isoformat() if end else date.today().isoformat()
            if start > end:
                raise ValueError('A data inicial precisa ser anterior ou igual à final.')
            with self._database() as db:
                # Transação de leitura: sessão e filhos pertencem à mesma versão.
                db.conn.execute('BEGIN')
                sessions = [dict(r, exercises=[], cardio=[]) for r in db.rows(
                    'SELECT * FROM workout_sessions WHERE day BETWEEN ? AND ? ORDER BY day DESC,id DESC', (start,end))]
                by_id = {s['id']:s for s in sessions}
                exercises = {}
                for row in db.rows('SELECT e.* FROM workout_exercises e JOIN workout_sessions w ON w.id=e.session_id WHERE w.day BETWEEN ? AND ? ORDER BY e.position', (start,end)):
                    exercise = dict(row, sets=[])
                    exercises[row['id']] = exercise
                    by_id[row['session_id']]['exercises'].append(exercise)
                for row in db.rows('SELECT s.* FROM workout_sets s JOIN workout_exercises e ON e.id=s.exercise_id JOIN workout_sessions w ON w.id=e.session_id WHERE w.day BETWEEN ? AND ? ORDER BY s.position', (start,end)):
                    exercises[row['exercise_id']]['sets'].append(dict(weight=row['weight_hundredths']/100, reps=row['reps']))
                for row in db.rows('SELECT c.* FROM workout_cardio c JOIN workout_sessions w ON w.id=c.session_id WHERE w.day BETWEEN ? AND ? ORDER BY c.position', (start,end)):
                    by_id[row['session_id']]['cardio'].append(dict(row, minutes=round(row['seconds']/60,2), distance_km=row['meters']/1000 if row['meters'] is not None else None))
                exercise_names = [r[0] for r in db.rows('SELECT MIN(name) FROM workout_exercises GROUP BY name_key ORDER BY name_key')]
                cardio_names = [r[0] for r in db.rows('SELECT MIN(name) FROM workout_cardio GROUP BY name_key ORDER BY name_key')]
            for session in sessions:
                session['metrics'] = session_metrics(session)
                session['metrics']['volume'] = float(session['metrics']['volume'])
            strength, cardio = trends(sessions)
            with self._database() as db:
                templates = [dict(r, **json.loads(r['body'])) for r in db.rows('SELECT * FROM workout_templates ORDER BY name COLLATE NOCASE')]
                for template in templates:
                    del template['body']
                last = {}
                # Última sessão de cada exercício, em todo o histórico, para sugerir a próxima carga.
                for row in db.rows('SELECT e.id,e.name_key,e.name,w.day FROM workout_exercises e JOIN workout_sessions w ON w.id=e.session_id ORDER BY w.day DESC, w.id DESC, e.position'):
                    if row['name_key'] in last:
                        continue
                    sets = [dict(weight=r['weight_hundredths'] / 100, reps=r['reps']) for r in db.rows('SELECT * FROM workout_sets WHERE exercise_id=? ORDER BY position', (row['id'],))]
                    top = max((s['weight'] for s in sets), default=0)
                    last[row['name_key']] = dict(name=row['name'], day=row['day'], sets=sets, suggested=suggested_weight(top))
            return dict(sessions=sessions, strength=strength, cardio=cardio, exercise_names=exercise_names, cardio_names=cardio_names,
                        templates=templates, last_exercises=last,
                        summary=dict(sessions=len(sessions), days=len({s['day'] for s in sessions}),
                                     volume=round(sum(s['metrics']['volume'] for s in sessions),2),
                                     cardio_minutes=round(sum(s['metrics']['cardio_minutes'] for s in sessions),2)))
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_workout_template(self, payload, item_id=None):
        try:
            name, body = validate_template(payload)
            with self._database() as db:
                if item_id is None:
                    item_id = db.write('INSERT INTO workout_templates(name,body,created) VALUES (?,?,?)',
                                       (name, json.dumps(body, ensure_ascii=False), datetime.now().isoformat(timespec='seconds')))
                else:
                    item_id = self._id(item_id)
                    if db.conn.execute('UPDATE workout_templates SET name=?,body=? WHERE id=?', (name, json.dumps(body, ensure_ascii=False), item_id)).rowcount != 1:
                        raise ValueError('Ficha não encontrada.')
                    db.conn.commit()
            return {'ok': True, 'id': item_id}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_workout_template(self, item_id):
        try:
            with self._database() as db, db.conn:
                if not db.conn.execute('DELETE FROM workout_templates WHERE id=?', (self._id(item_id),)).rowcount:
                    raise ValueError('Ficha não encontrada.')
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}
