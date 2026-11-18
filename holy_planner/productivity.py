"""Planejamento, metas, notas e sessões de foco, sem serviços externos."""
import re
import sqlite3
from datetime import date, datetime, timedelta


def initialize_schema(conn):
    columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)')}
    for name, definition in {
        'estimate_minutes': 'INTEGER NOT NULL DEFAULT 0',
        'scheduled_time': "TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in columns:
            conn.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            target INTEGER NOT NULL DEFAULT 1, current INTEGER NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'etapas', due TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
            updated TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id TEXT PRIMARY KEY, task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            title TEXT NOT NULL, minutes INTEGER NOT NULL, day TEXT NOT NULL,
            completed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_focus_day ON focus_sessions(day);
    ''')
    conn.commit()


def bounded_integer(value, minimum, maximum, label):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError(f'{label}: informe um número inteiro.')
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f'{label}: use um valor entre {minimum} e {maximum}.')
    return value


def text_value(payload, key, limit, required=False):
    value = payload.get(key, '')
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'Preencha {key} corretamente (até {limit} caracteres).')
    return value.strip()


class ProductivityApi:
    def productivity_snapshot(self):
        today = date.today()
        first = today - timedelta(days=today.weekday())
        with self._database() as db:
            sessions = db.rows('SELECT * FROM focus_sessions ORDER BY completed_at DESC LIMIT 100')
            week = dict(db.rows('SELECT day, SUM(minutes) FROM focus_sessions WHERE day BETWEEN ? AND ? GROUP BY day',
                               (first.isoformat(), (first + timedelta(days=6)).isoformat())))
            from .life import goal_progress
            goals = []
            for row in db.rows('SELECT * FROM goals ORDER BY due="", due, id DESC'):
                goal = dict(row)
                goal['auto'] = goal.get('source', 'manual') != 'manual'
                goal['current'] = goal_progress(db, row, today)
                goals.append(goal)
            goals.sort(key=lambda g: g['current'] >= g['target'])
            return {
                'goals': goals,
                'notes': [dict(r) for r in db.rows('SELECT * FROM notes ORDER BY pinned DESC, updated DESC, id DESC')],
                'sessions': [dict(r) for r in sessions],
                'focus_today': week.get(today.isoformat(), 0),
                'focus_week': sum(week.values()),
                'focus_days': [{'day': (first + timedelta(days=i)).isoformat(),
                                'minutes': week.get((first + timedelta(days=i)).isoformat(), 0)} for i in range(7)],
            }

    def save_productivity(self, table, payload, item_id=None):
        try:
            if table not in ('goals', 'notes') or not isinstance(payload, dict):
                raise ValueError('Registro inválido.')
            values = {'title': text_value(payload, 'title', 200, True)}
            if table == 'goals':
                due = text_value(payload, 'due', 10)
                from .life import validate_goal_source
                link = validate_goal_source(payload)
                values.update(description=text_value(payload, 'description', 10000),
                              target=bounded_integer(payload.get('target', 1), 1, 1000000000, 'Meta'),
                              current=bounded_integer(payload.get('current', 0) if link['source'] == 'manual' else 0, 0, 1000000000, 'Progresso'),
                              **link,
                              unit=text_value(payload, 'unit', 40, True),
                              due=date.fromisoformat(due).isoformat() if due else '')
            else:
                values.update(body=text_value(payload, 'body', 30000), updated=datetime.now().isoformat(),
                              pinned=bounded_integer(payload.get('pinned', 0), 0, 1, 'Fixar'))
            with self._database() as db:
                if item_id is None:
                    item_id = db.write(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
                else:
                    item_id = self._id(item_id)
                    if not db.rows(f'SELECT id FROM {table} WHERE id=?', (item_id,)):
                        raise ValueError('Registro não encontrado. Atualize a tela.')
                    db.write(f"UPDATE {table} SET {','.join(f'{key}=?' for key in values)} WHERE id=?", (*values.values(), item_id))
            return {'ok': True, 'id': item_id}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_productivity(self, table, item_id):
        try:
            if table not in ('goals', 'notes'):
                raise ValueError('Registro inválido.')
            with self._database() as db:
                if not db.rows(f'SELECT id FROM {table} WHERE id=?', (self._id(item_id),)):
                    raise ValueError('Registro não encontrado.')
                db.write(f'DELETE FROM {table} WHERE id=?', (self._id(item_id),))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def set_task_status(self, item_id, status):
        try:
            if status not in ('A fazer', 'Em andamento', 'Concluído'):
                raise ValueError('Status inválido.')
            with self._database() as db:
                if not db.rows('SELECT id FROM tasks WHERE id=?', (self._id(item_id),)):
                    raise ValueError('Tarefa não encontrada.')
                db.write('UPDATE tasks SET status=? WHERE id=?', (status, self._id(item_id)))
            return {'ok': True, 'warning': self._schedule_google()}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_focus_session(self, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError('Sessão inválida.')
            session_id = text_value(payload, 'id', 80, True)
            if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', session_id):
                raise ValueError('Identificador da sessão inválido.')
            minutes = bounded_integer(payload.get('minutes'), 1, 180, 'Minutos')
            day = date.fromisoformat(text_value(payload, 'day', 10, True))
            if day > date.today():
                raise ValueError('A sessão não pode estar no futuro.')
            title = text_value(payload, 'title', 200) or 'Foco livre'
            with self._database() as db:
                task_id = payload.get('task_id')
                if task_id not in (None, ''):
                    task_id = self._id(task_id)
                    if not db.rows('SELECT id FROM tasks WHERE id=?', (task_id,)):
                        task_id = None  # A tarefa pode ter sido excluída durante o foco.
                else:
                    task_id = None
                db.write('INSERT OR IGNORE INTO focus_sessions VALUES (?,?,?,?,?,?)',
                         (session_id, task_id, title, minutes, day.isoformat(), datetime.now().isoformat()))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}
