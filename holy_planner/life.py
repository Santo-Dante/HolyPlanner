"""Holy Planner 5.0: lembretes, revisão semanal, diário e ligações entre áreas.

Tudo é calculado a partir dos registros locais. Nada aqui chama serviços externos,
exceto a notificação do Windows, que usa o próprio sistema operacional.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import finance
GOAL_SOURCES = ('manual', 'workouts', 'focus', 'routine', 'wealth')
GOAL_PERIODS = ('week', 'month', 'total')
SETTINGS = {
    'reminders_enabled': '1',
    'reminder_hour': '20',
    'system_notifications': '1',
}
TOAST_APP_ID = r'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'


def initialize_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS weekly_reviews (
            week TEXT PRIMARY KEY, wins TEXT NOT NULL DEFAULT '', lessons TEXT NOT NULL DEFAULT '',
            priorities TEXT NOT NULL DEFAULT '[]', updated TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journal (
            day TEXT PRIMARY KEY,
            mood INTEGER CHECK(mood BETWEEN 1 AND 5), energy INTEGER CHECK(energy BETWEEN 1 AND 5),
            sleep_tenths INTEGER CHECK(sleep_tenths BETWEEN 0 AND 240),
            note TEXT NOT NULL DEFAULT ''
        );
    ''')
    add_columns(conn, 'goals', {'source': "TEXT NOT NULL DEFAULT 'manual'", 'source_ref': 'INTEGER NOT NULL DEFAULT 0',
                                'period': "TEXT NOT NULL DEFAULT 'total'"})
    add_columns(conn, 'routines', {'auto_workout': 'INTEGER NOT NULL DEFAULT 0'})
    add_columns(conn, 'tasks', {'completed_at': "TEXT NOT NULL DEFAULT ''"})
    add_columns(conn, 'finance_transactions', {'series': "TEXT NOT NULL DEFAULT ''", 'import_key': "TEXT NOT NULL DEFAULT ''"})
    # Data de conclusão das tarefas, usada pela revisão semanal (vale para todos os caminhos de gravação).
    conn.executescript('''
        CREATE TRIGGER IF NOT EXISTS tasks_completed_update AFTER UPDATE OF status ON tasks WHEN NEW.status <> OLD.status
        BEGIN UPDATE tasks SET completed_at = CASE WHEN NEW.status='Concluído' THEN datetime('now','localtime') ELSE '' END WHERE id=NEW.id; END;
        CREATE TRIGGER IF NOT EXISTS tasks_completed_insert AFTER INSERT ON tasks WHEN NEW.status='Concluído'
        BEGIN UPDATE tasks SET completed_at=datetime('now','localtime') WHERE id=NEW.id; END;
    ''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finance_series ON finance_transactions(series) WHERE series<>''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_finance_import ON finance_transactions(import_key) WHERE import_key<>''")
    conn.commit()


def add_columns(conn, table, columns):
    existing = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def monday(day: date):
    return day - timedelta(days=day.weekday())


def period_bounds(period, today):
    if period == 'week':
        first = monday(today)
        return first.isoformat(), (first + timedelta(days=6)).isoformat()
    if period == 'month':
        first, last = finance.month_bounds(today.strftime('%Y-%m'))
        return first, last
    return '0001-01-01', '9999-12-31'


def routine_scheduled(routine, day: date):
    return routine['created'] <= day.isoformat() and str(day.weekday()) in routine['days'].split(',')


# ---------------------------------------------------------------- metas automáticas
def goal_progress(db, goal, today=None):
    """Valor atual de uma meta ligada a outra área do aplicativo."""
    today = today or date.today()
    source = goal['source'] if 'source' in goal.keys() else 'manual'
    if source == 'manual':
        return goal['current']
    first, last = period_bounds(goal['period'], today)
    if source == 'workouts':
        return db.rows('SELECT COUNT(*) FROM workout_sessions WHERE day BETWEEN ? AND ?', (first, last))[0][0]
    if source == 'focus':
        return db.rows('SELECT COALESCE(SUM(minutes),0) FROM focus_sessions WHERE day BETWEEN ? AND ?', (first, last))[0][0]
    if source == 'routine':
        return db.rows('SELECT COUNT(*) FROM checks WHERE routine_id=? AND day BETWEEN ? AND ?',
                       (goal['source_ref'], first, last))[0][0]
    if source == 'wealth':
        row = db.rows('SELECT amount_cents FROM investment_snapshots ORDER BY day DESC LIMIT 1')
        return row[0][0] // 100 if row else 0
    return goal['current']


def validate_goal_source(payload):
    source = payload.get('source') or 'manual'
    period = payload.get('period') or 'total'
    if source not in GOAL_SOURCES or period not in GOAL_PERIODS:
        raise ValueError('Origem ou período da meta inválidos.')
    ref = 0
    if source == 'routine':
        raw = payload.get('source_ref')
        if isinstance(raw, bool) or not re.fullmatch(r'[1-9][0-9]{0,9}', str(raw or '')):
            raise ValueError('Escolha a rotina que alimenta esta meta.')
        ref = int(raw)
    return dict(source=source, source_ref=ref, period='total' if source == 'wealth' else period)


# ---------------------------------------------------------------- diário
def validate_journal(payload, existing=None):
    if not isinstance(payload, dict):
        raise ValueError('Registro do diário inválido.')
    raw = payload.get('day')
    if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        raise ValueError('Informe a data do diário.')
    day = date.fromisoformat(raw)
    if day > date.today():
        raise ValueError('O diário aceita hoje e datas passadas.')
    values = dict(existing or {'mood': None, 'energy': None, 'sleep_tenths': None, 'note': ''})
    for key, label in (('mood', 'Humor'), ('energy', 'Energia')):
        if key in payload:
            value = payload[key]
            if value in ('', None):
                values[key] = None
            elif isinstance(value, bool) or str(value) not in ('1', '2', '3', '4', '5'):
                raise ValueError(f'{label}: escolha de 1 a 5.')
            else:
                values[key] = int(value)
    if 'sleep' in payload:
        value = str(payload['sleep'] if payload['sleep'] is not None else '').strip().replace(',', '.')
        if not value:
            values['sleep_tenths'] = None
        elif not re.fullmatch(r'\d{1,2}(?:\.\d)?', value) or float(value) > 24:
            raise ValueError('Sono: informe as horas, por exemplo 7,5.')
        else:
            values['sleep_tenths'] = round(float(value) * 10)
    if 'note' in payload:
        values['note'] = finance.text_field(payload, 'note', 5000)
    return day.isoformat(), values


def average(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def journal_insights(entries, workout_days, focus_by_day, routine_days):
    """Comparações simples entre grupos de dias; exige pelo menos 3 dias em cada grupo."""
    insights = []

    def compare(key, label, unit, metric, in_group, a_label, b_label):
        a = [metric(e) for e in entries if in_group(e) and metric(e) is not None]
        b = [metric(e) for e in entries if not in_group(e) and metric(e) is not None]
        if len(a) >= 3 and len(b) >= 3:
            insights.append(dict(key=key, label=label, unit=unit, a_label=a_label, a_value=average(a), a_count=len(a),
                                 b_label=b_label, b_value=average(b), b_count=len(b)))

    compare('mood_workout', 'Humor em dias com treino', 'de 5', lambda e: e['mood'],
            lambda e: e['day'] in workout_days, 'Com treino', 'Sem treino')
    compare('energy_sleep', 'Energia depois de dormir 7h ou mais', 'de 5', lambda e: e['energy'],
            lambda e: (e['sleep_tenths'] or 0) >= 70 if e['sleep_tenths'] is not None else False, '7h ou mais', 'Menos de 7h')
    compare('focus_sleep', 'Minutos de foco depois de dormir 7h ou mais', 'min',
            lambda e: focus_by_day.get(e['day'], 0) if e['sleep_tenths'] is not None else None,
            lambda e: (e['sleep_tenths'] or 0) >= 70, '7h ou mais', 'Menos de 7h')
    compare('mood_routines', 'Humor em dias com todas as rotinas feitas', 'de 5', lambda e: e['mood'],
            lambda e: e['day'] in routine_days, 'Rotinas completas', 'Rotinas incompletas')
    return insights


# ---------------------------------------------------------------- notificações do Windows
def windows_toast(title, body, runner=None):
    """Mostra uma notificação nativa do Windows via PowerShell, sem dependências extras."""
    if sys.platform != 'win32' and runner is None:
        return False
    script = (
        "$ErrorActionPreference='Stop';"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$t=[Security.SecurityElement]::Escape($env:HP_TITLE);$b=[Security.SecurityElement]::Escape($env:HP_BODY);"
        "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;"
        "$x.LoadXml(\"<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$b</text></binding></visual></toast>\");"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{TOAST_APP_ID}').Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    env = {**os.environ, 'HP_TITLE': title[:120], 'HP_BODY': body[:300]}
    command = ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-Command', script]
    (runner or subprocess.Popen)(command, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def startup_file():
    base = os.environ.get('APPDATA')
    if not base:
        return None
    return Path(base) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup' / 'Holy Planner.cmd'


def startup_command():
    if getattr(sys, 'frozen', False):
        return f'start "" "{sys.executable}"'
    folder = Path(__file__).resolve().parent.parent
    pythonw = folder / '.venv' / 'Scripts' / 'pythonw.exe'
    return f'cd /d "{folder}"\r\nstart "" "{pythonw}" "{folder / "app.py"}"'


class LifeApi:
    # ---------------------------------------------------------- configurações
    def _settings(self, db):
        values = dict(SETTINGS)
        values.update({r['key']: r['value'] for r in db.rows('SELECT key,value FROM app_settings')})
        return values

    def app_settings(self):
        try:
            with self._database() as db:
                values = self._settings(db)
            target = startup_file()
            return {'ok': True, 'reminders_enabled': values['reminders_enabled'] == '1',
                    'reminder_hour': int(values['reminder_hour']),
                    'system_notifications': values['system_notifications'] == '1',
                    'autostart': bool(target and target.exists()), 'autostart_available': bool(target) and sys.platform == 'win32'}
        except (ValueError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_app_settings(self, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError('Configurações inválidas.')
            values = {}
            for key in ('reminders_enabled', 'system_notifications'):
                if key in payload:
                    if not isinstance(payload[key], bool):
                        raise ValueError('Opção inválida.')
                    values[key] = '1' if payload[key] else '0'
            if 'reminder_hour' in payload:
                hour = payload['reminder_hour']
                if isinstance(hour, bool) or not re.fullmatch(r'\d{1,2}', str(hour)) or not 0 <= int(hour) <= 23:
                    raise ValueError('Escolha um horário entre 0 e 23 horas.')
                values['reminder_hour'] = str(int(hour))
            with self._database() as db, db.conn:
                db.conn.executemany('INSERT INTO app_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                                    list(values.items()))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def set_autostart(self, enabled):
        """Cria ou remove o atalho na pasta Inicializar do Windows (só na janela desktop)."""
        try:
            if not isinstance(enabled, bool):
                raise ValueError('Opção inválida.')
            target = startup_file()
            if target is None:
                raise ValueError('Disponível apenas no Windows.')
            if enabled:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('@echo off\r\n' + startup_command() + '\r\n', encoding='utf-8')
            elif target.exists():
                target.unlink()
            return {'ok': True, 'autostart': enabled}
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}

    def notify(self, title, body):
        """Notificação nativa; chamada só pela janela desktop (fora da lista do servidor web)."""
        try:
            if not isinstance(title, str) or not isinstance(body, str):
                raise ValueError('Notificação inválida.')
            runner = getattr(self, '_toast_runner', None)
            return {'ok': True, 'shown': windows_toast(title, body, runner)}
        except (ValueError, OSError) as exc:
            return {'ok': False, 'error': str(exc)}

    # ---------------------------------------------------------- lembretes
    def reminders(self, now=None):
        try:
            now = now or datetime.now()
            today = now.date()
            iso = today.isoformat()
            with self._database() as db:
                settings = self._settings(db)
                if settings['reminders_enabled'] != '1':
                    return {'ok': True, 'items': [], 'settings': settings}
                hour = int(settings['reminder_hour'])
                items = []
                tasks_today = db.rows("SELECT COUNT(*) FROM tasks WHERE due=? AND status<>'Concluído'", (iso,))[0][0]
                overdue = db.rows("SELECT COUNT(*) FROM tasks WHERE due<>'' AND due<? AND status<>'Concluído'", (iso,))[0][0]
                if tasks_today:
                    items.append(dict(key=f'tasks-{iso}', kind='tasks', page='today', title=f'{tasks_today} tarefa(s) para hoje',
                                      detail='Escolha a mais importante e comece por ela.'))
                if overdue:
                    items.append(dict(key=f'overdue-{iso}', kind='tasks', page='tasks', title=f'{overdue} tarefa(s) atrasada(s)',
                                      detail='Reagende ou conclua para limpar o radar.'))
                if now.hour >= hour:
                    open_routines = [r['title'] for r in db.routines_on(today) if not r['done']]
                    if open_routines:
                        names = ', '.join(open_routines[:3]) + ('…' if len(open_routines) > 3 else '')
                        items.append(dict(key=f'routines-{iso}', kind='routines', page='routines',
                                          title=f'{len(open_routines)} rotina(s) ainda abertas hoje', detail=names))
                    if not db.rows('SELECT 1 FROM journal WHERE day=?', (iso,)):
                        items.append(dict(key=f'journal-{iso}', kind='journal', page='journal', title='Como foi o seu dia?',
                                          detail='Registre humor, energia e sono em poucos segundos.'))
                tomorrow = (today + timedelta(days=1)).isoformat()
                for row in db.rows("SELECT title,amount_cents,day,kind FROM finance_transactions WHERE status='pending' "
                                   "AND kind IN ('expense','investment') AND day BETWEEN ? AND ? ORDER BY day, amount_cents DESC",
                                   (iso, tomorrow)):
                    when = 'hoje' if row['day'] == iso else 'amanhã'
                    items.append(dict(key=f"bill-{row['day']}-{row['title']}-{row['amount_cents']}", kind='finance', page='finance',
                                      title=f"{row['title']} vence {when}", detail=f"Previsto: {money_text(row['amount_cents'])}"))
                late_bills = db.rows("SELECT COUNT(*) FROM finance_transactions WHERE status='pending' AND day<?", (iso,))[0][0]
                if late_bills:
                    items.append(dict(key=f'late-bills-{iso}', kind='finance', page='finance', title=f'{late_bills} lançamento(s) previsto(s) vencido(s)',
                                      detail='Efetive o que já aconteceu ou ajuste a data.'))
                uses_planning = db.rows('SELECT (SELECT COUNT(*) FROM investment_snapshots)+(SELECT COUNT(*) FROM investment_scenarios)')[0][0]
                month = today.strftime('%Y-%m')
                if uses_planning and today.day >= 25 and not db.rows('SELECT 1 FROM investment_snapshots WHERE substr(day,1,7)=?', (month,)):
                    items.append(dict(key=f'wealth-{month}', kind='planning', page='planning', title='Registre o valor da carteira do mês',
                                      detail='Leva menos de um minuto e mantém seu gráfico atualizado.'))
                week = review_week_for(today)
                if week and not db.rows('SELECT 1 FROM weekly_reviews WHERE week=?', (week,)):
                    items.append(dict(key=f'review-{week}', kind='review', page='review', title='Hora da revisão da semana',
                                      detail='10 minutos para olhar a semana e planejar a próxima.'))
            return {'ok': True, 'items': items, 'settings': settings}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    # ---------------------------------------------------------- revisão semanal
    def review_snapshot(self, week=None):
        try:
            today = date.today()
            first = date.fromisoformat(week) if week else review_target(today)
            if first.weekday() != 0:
                raise ValueError('A semana deve começar na segunda-feira.')
            last = first + timedelta(days=6)
            a, b = first.isoformat(), last.isoformat()
            next_first, next_last = (first + timedelta(days=7)).isoformat(), (first + timedelta(days=13)).isoformat()
            with self._database() as db:
                done = [dict(r) for r in db.rows("SELECT id,title,due FROM tasks WHERE status='Concluído' AND substr(completed_at,1,10) BETWEEN ? AND ? ORDER BY completed_at", (a, b))]
                missed = [dict(r) for r in db.rows("SELECT id,title,due,priority FROM tasks WHERE status<>'Concluído' AND due<>'' AND due<=? ORDER BY due", (b,))]
                routines = [dict(r) for r in db.rows('SELECT * FROM routines')]
                checks = {(r['routine_id'], r['day']) for r in db.rows('SELECT routine_id,day FROM checks WHERE day BETWEEN ? AND ?', (a, b))}
                scheduled = completed = 0
                per_routine = []
                for routine in routines:
                    total = hit = 0
                    for offset in range(7):
                        current = first + timedelta(days=offset)
                        if current > today or not routine_scheduled(routine, current):
                            continue
                        total += 1
                        hit += (routine['id'], current.isoformat()) in checks
                    if total:
                        per_routine.append(dict(title=routine['title'], scheduled=total, done=hit))
                    scheduled += total
                    completed += hit
                focus = db.rows('SELECT COALESCE(SUM(minutes),0), COUNT(*) FROM focus_sessions WHERE day BETWEEN ? AND ?', (a, b))[0]
                workouts = db.rows('SELECT COUNT(*) FROM workout_sessions WHERE day BETWEEN ? AND ?', (a, b))[0][0]
                cardio = db.rows('SELECT COALESCE(SUM(c.seconds),0) FROM workout_cardio c JOIN workout_sessions s ON s.id=c.session_id WHERE s.day BETWEEN ? AND ?', (a, b))[0][0]
                money = {k: 0 for k in finance.KINDS}
                for row in db.rows("SELECT kind,SUM(amount_cents) AS total FROM finance_transactions WHERE status='paid' AND day BETWEEN ? AND ? GROUP BY kind", (a, b)):
                    money[row['kind']] = row['total']
                categories = [dict(r) for r in db.rows("SELECT category,SUM(amount_cents) AS total FROM finance_transactions WHERE status='paid' AND kind='expense' AND day BETWEEN ? AND ? GROUP BY category ORDER BY total DESC LIMIT 3", (a, b))]
                journal = [dict(r) for r in db.rows('SELECT * FROM journal WHERE day BETWEEN ? AND ?', (a, b))]
                saved = db.rows('SELECT * FROM weekly_reviews WHERE week=?', (a,))
                undated = [dict(r) for r in db.rows("SELECT id,title,priority,estimate_minutes FROM tasks WHERE due='' AND status<>'Concluído' ORDER BY priority='Alta' DESC, id DESC LIMIT 40")]
                upcoming = [dict(r) for r in db.rows("SELECT id,title,due,priority FROM tasks WHERE status<>'Concluído' AND due BETWEEN ? AND ? ORDER BY due", (next_first, next_last))]
                bills = [dict(r) for r in db.rows("SELECT title,day,amount_cents,kind FROM finance_transactions WHERE status='pending' AND day BETWEEN ? AND ? ORDER BY day", (next_first, next_last))]
            review = dict(saved[0]) if saved else {'week': a, 'wins': '', 'lessons': '', 'priorities': '[]', 'updated': ''}
            review['priorities'] = json.loads(review['priorities'] or '[]')
            return {'week': a, 'end': b, 'next_week': next_first, 'next_end': next_last, 'today': today.isoformat(),
                    'tasks_done': done, 'tasks_missed': missed, 'routines': dict(scheduled=scheduled, done=completed, items=per_routine),
                    'focus_minutes': focus[0], 'focus_sessions': focus[1], 'workouts': workouts, 'cardio_minutes': round(cardio / 60),
                    'money': dict(income=money['income'] + money['yield'], expense=money['expense'], invested=money['investment'] - money['redemption'],
                                  categories=categories),
                    'journal': dict(days=len(journal), mood=average([j['mood'] for j in journal]), energy=average([j['energy'] for j in journal]),
                                    sleep=average([j['sleep_tenths'] / 10 if j['sleep_tenths'] is not None else None for j in journal])),
                    'review': review, 'undated': undated, 'upcoming': upcoming, 'bills': bills}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_review(self, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError('Revisão inválida.')
            first = date.fromisoformat(str(payload.get('week', '')))
            if first.weekday() != 0:
                raise ValueError('A semana deve começar na segunda-feira.')
            priorities = payload.get('priorities', [])
            if not isinstance(priorities, list) or len(priorities) > 3 or any(not isinstance(p, str) or len(p) > 200 for p in priorities):
                raise ValueError('Escolha até 3 prioridades com até 200 caracteres.')
            priorities = [p.strip() for p in priorities if p.strip()]
            wins = finance.text_field(payload, 'wins', 5000)
            lessons = finance.text_field(payload, 'lessons', 5000)
            with self._database() as db:
                db.write('INSERT INTO weekly_reviews(week,wins,lessons,priorities,updated) VALUES (?,?,?,?,?) '
                         'ON CONFLICT(week) DO UPDATE SET wins=excluded.wins, lessons=excluded.lessons, priorities=excluded.priorities, updated=excluded.updated',
                         (first.isoformat(), wins, lessons, json.dumps(priorities, ensure_ascii=False), datetime.now().isoformat(timespec='seconds')))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def schedule_tasks(self, assignments):
        """Define o prazo de várias tarefas de uma vez (planejamento da próxima semana)."""
        try:
            if not isinstance(assignments, list) or len(assignments) > 100:
                raise ValueError('Planejamento inválido.')
            rows = []
            for item in assignments:
                if not isinstance(item, dict):
                    raise ValueError('Planejamento inválido.')
                due = str(item.get('due') or '')
                rows.append((date.fromisoformat(due).isoformat() if due else '', self._id(item.get('id'))))
            with self._database() as db, db.conn:
                for due, item_id in rows:
                    if db.conn.execute('UPDATE tasks SET due=? WHERE id=?', (due, item_id)).rowcount != 1:
                        raise ValueError('Uma das tarefas não foi encontrada. Atualize a tela.')
            return {'ok': True, 'count': len(rows), 'warning': self._schedule_google() if rows else ''}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    # ---------------------------------------------------------- diário
    def save_journal(self, payload):
        try:
            with self._database() as db:
                day = payload.get('day') if isinstance(payload, dict) else None
                current = db.rows('SELECT mood,energy,sleep_tenths,note FROM journal WHERE day=?', (day,)) if isinstance(day, str) else []
                day, values = validate_journal(payload, dict(current[0]) if current else None)
                db.write('INSERT INTO journal(day,mood,energy,sleep_tenths,note) VALUES (?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET '
                         'mood=excluded.mood, energy=excluded.energy, sleep_tenths=excluded.sleep_tenths, note=excluded.note',
                         (day, values['mood'], values['energy'], values['sleep_tenths'], values['note']))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_journal(self, day):
        try:
            day = date.fromisoformat(str(day)).isoformat()
            with self._database() as db:
                if not db.rows('SELECT 1 FROM journal WHERE day=?', (day,)):
                    raise ValueError('Registro não encontrado.')
                db.write('DELETE FROM journal WHERE day=?', (day,))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def journal_snapshot(self, days=90):
        try:
            if isinstance(days, bool) or not isinstance(days, int) or not 7 <= days <= 3650:
                raise ValueError('Período inválido.')
            today = date.today()
            start = (today - timedelta(days=days - 1)).isoformat()
            with self._database() as db:
                entries = [dict(r) for r in db.rows('SELECT * FROM journal WHERE day>=? ORDER BY day DESC', (start,))]
                workout_days = {r[0] for r in db.rows('SELECT DISTINCT day FROM workout_sessions WHERE day>=?', (start,))}
                focus = dict(db.rows('SELECT day,SUM(minutes) FROM focus_sessions WHERE day>=? GROUP BY day', (start,)))
                routines = [dict(r) for r in db.rows('SELECT * FROM routines')]
                checks = {(r[0], r[1]) for r in db.rows('SELECT routine_id,day FROM checks WHERE day>=?', (start,))}
            routine_days = set()
            for entry in entries:
                current = date.fromisoformat(entry['day'])
                scheduled = [r for r in routines if routine_scheduled(r, current)]
                if scheduled and all((r['id'], entry['day']) in checks for r in scheduled):
                    routine_days.add(entry['day'])
            for entry in entries:
                entry['sleep'] = entry['sleep_tenths'] / 10 if entry['sleep_tenths'] is not None else None
                entry['workout'] = entry['day'] in workout_days
                entry['focus_minutes'] = focus.get(entry['day'], 0)
            today_entry = next((e for e in entries if e['day'] == today.isoformat()), None)
            return {'today': today.isoformat(), 'entry': today_entry, 'entries': entries,
                    'averages': dict(mood=average([e['mood'] for e in entries]), energy=average([e['energy'] for e in entries]),
                                     sleep=average([e['sleep'] for e in entries])),
                    'insights': journal_insights(entries, workout_days, focus, routine_days)}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    # ---------------------------------------------------------- ligação treino → rotina
    def _auto_check_workout(self, day):
        """Marca as rotinas configuradas para concluir quando um treino é registrado."""
        current = date.fromisoformat(day)
        with self._database() as db, db.conn:
            for routine in db.rows('SELECT * FROM routines WHERE auto_workout=1'):
                if routine_scheduled(routine, current):
                    db.conn.execute('INSERT OR IGNORE INTO checks VALUES (?,?)', (routine['id'], day))


def review_target(today):
    """Domingo e segunda revisam a semana que termina/terminou; nos outros dias, a semana atual."""
    if today.weekday() == 0:
        return monday(today) - timedelta(days=7)
    return monday(today)


def review_week_for(today):
    """Semana cuja revisão deve ser lembrada hoje (domingo ou segunda)."""
    if today.weekday() == 6:
        return monday(today).isoformat()
    if today.weekday() == 0:
        return (monday(today) - timedelta(days=7)).isoformat()
    return None


def money_text(cents):
    sign = '-' if cents < 0 else ''
    cents = abs(cents)
    return f"{sign}R$ {cents // 100:,}".replace(',', '.') + f",{cents % 100:02d}"
