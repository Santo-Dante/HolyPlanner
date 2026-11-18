"""Planejamento de investimentos: histórico registrado e cenários fictícios.

Os cenários são simulações informadas pelo usuário. Nada aqui é enviado a
serviços externos, e nenhum cenário altera os lançamentos financeiros.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime

from . import finance
from . import investidor10
START_MODES = ('snapshot', 'capital', 'custom')
EVENT_KINDS = ('deposit', 'withdrawal')
MAX_EVENTS = 60
MAX_HISTORY_MONTHS = 600


def initialize_schema(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS investment_snapshots (
            id INTEGER PRIMARY KEY, day TEXT NOT NULL UNIQUE,
            amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS investment_scenarios (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            start_mode TEXT NOT NULL CHECK(start_mode IN ('snapshot','capital','custom')),
            start_cents INTEGER NOT NULL DEFAULT 0 CHECK(start_cents >= 0),
            monthly_cents INTEGER NOT NULL DEFAULT 0 CHECK(monthly_cents >= 0),
            annual_rate_bp INTEGER NOT NULL DEFAULT 0,
            inflation_bp INTEGER NOT NULL DEFAULT 0,
            raise_bp INTEGER NOT NULL DEFAULT 0,
            years INTEGER NOT NULL CHECK(years BETWEEN 1 AND 60),
            target_cents INTEGER NOT NULL DEFAULT 0 CHECK(target_cents >= 0),
            visible INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS investment_scenario_events (
            id INTEGER PRIMARY KEY,
            scenario_id INTEGER NOT NULL REFERENCES investment_scenarios(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, title TEXT NOT NULL, month TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            yearly INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_scenario_events ON investment_scenario_events(scenario_id);
    ''')
    conn.commit()


def percent_bp(value, label, minimum, maximum):
    """Converte '10,5' em 1050 centésimos de ponto percentual."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'{label}: informe um percentual, por exemplo 10,5.')
    raw = str(value).strip().replace(',', '.') or '0'
    if not re.fullmatch(r'-?\d{1,3}(?:\.\d{1,2})?', raw):
        raise ValueError(f'{label}: use até duas casas decimais, por exemplo 10,5.')
    bp = round(float(raw) * 100)
    if not minimum * 100 <= bp <= maximum * 100:
        raise ValueError(f'{label}: use um valor entre {minimum}% e {maximum}%.')
    return bp


def validate_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError('Dados do registro inválidos.')
    raw = payload.get('day')
    if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        raise ValueError('Informe uma data válida.')
    day = date.fromisoformat(raw)
    if day > date.today() or day.year < 1900:
        raise ValueError('Registre o valor da carteira em uma data até hoje.')
    return dict(day=day.isoformat(),
                amount_cents=finance.money_cents(payload.get('amount'), positive=False),
                notes=finance.text_field(payload, 'notes', 2000))


def validate_scenario(payload):
    if not isinstance(payload, dict):
        raise ValueError('Dados do cenário inválidos.')
    mode = payload.get('start_mode', 'snapshot')
    if mode not in START_MODES:
        raise ValueError('Ponto de partida inválido.')
    years = payload.get('years')
    if isinstance(years, bool) or not re.fullmatch(r'\d{1,2}', str(years)) or not 1 <= int(years) <= 60:
        raise ValueError('Prazo: escolha de 1 a 60 anos.')
    events = payload.get('events', [])
    if not isinstance(events, list) or len(events) > MAX_EVENTS or any(not isinstance(e, dict) for e in events):
        raise ValueError(f'Use até {MAX_EVENTS} eventos por cenário.')
    result = dict(
        name=finance.text_field(payload, 'name', 80, True),
        start_mode=mode,
        start_cents=finance.money_cents(payload.get('start') or '0', positive=False) if mode == 'custom' else 0,
        monthly_cents=finance.money_cents(payload.get('monthly') or '0', positive=False),
        annual_rate_bp=percent_bp(payload.get('annual_rate', '0'), 'Rentabilidade anual', -50, 100),
        inflation_bp=percent_bp(payload.get('inflation', '0'), 'Inflação anual', -20, 100),
        raise_bp=percent_bp(payload.get('raise', '0'), 'Reajuste anual do aporte', -50, 100),
        years=int(years),
        target_cents=finance.money_cents(payload.get('target') or '0', positive=False),
        visible=0 if payload.get('visible') in (0, '0', False) else 1,
        notes=finance.text_field(payload, 'notes', 2000),
        events=[],
    )
    for event in events:
        month = event.get('month')
        finance.month_bounds(month)
        kind = event.get('kind')
        if kind not in EVENT_KINDS:
            raise ValueError('Tipo de evento inválido.')
        result['events'].append(dict(
            title=finance.text_field(event, 'title', 120, True), month=month, kind=kind,
            amount_cents=finance.money_cents(event.get('amount')),
            yearly=1 if event.get('yearly') in (1, '1', True, 'on') else 0))
    return result


def month_key(value: date):
    return f'{value.year:04d}-{value.month:02d}'


def next_month(key):
    year, month = map(int, key.split('-'))
    return f'{year + month // 12:04d}-{month % 12 + 1:02d}'


def history(db, today=None):
    """Capital registrado no fim de cada mês e registros de valor da carteira."""
    today = today or date.today()
    settings = dict(db.rows('SELECT * FROM finance_settings WHERE id=1')[0])
    movements = db.rows("SELECT substr(day,1,7) AS month, kind, SUM(amount_cents) AS total "
                        "FROM finance_transactions WHERE status='paid' AND day<=? "
                        "AND kind IN ('investment','redemption','yield') GROUP BY month, kind ORDER BY month",
                        (today.isoformat(),))
    snapshots = [dict(r) for r in db.rows('SELECT * FROM investment_snapshots ORDER BY day')]
    first = min([r['month'] for r in movements] + [s['day'][:7] for s in snapshots], default=None)
    current = month_key(today)
    by_month = {}
    for row in movements:
        by_month.setdefault(row['month'], {})[row['kind']] = row['total']
    series = []
    if first:
        capital, yields, key = settings['opening_invested_cents'], 0, first
        months = []
        while key <= current:
            months.append(key)
            key = next_month(key)
        # Mantém o desenho legível em históricos muito longos.
        skipped = months[:-MAX_HISTORY_MONTHS]
        for key in skipped:
            values = by_month.get(key, {})
            capital += values.get('investment', 0) - values.get('redemption', 0)
            yields += values.get('yield', 0)
        for key in months[-MAX_HISTORY_MONTHS:]:
            values = by_month.get(key, {})
            net = values.get('investment', 0) - values.get('redemption', 0)
            capital += net
            yields += values.get('yield', 0)
            series.append(dict(month=key, capital_cents=capital, net_cents=net, yield_cents=yields))
    # Média dos aportes líquidos dos seis meses completos anteriores.
    previous, key = [], current
    for _ in range(6):
        year, month = map(int, key.split('-'))
        key = f'{year - (month == 1):04d}-{(month - 2) % 12 + 1:02d}'
        values = by_month.get(key, {})
        previous.append(values.get('investment', 0) - values.get('redemption', 0))
    capital_now = settings['opening_invested_cents'] + sum(
        v.get('investment', 0) - v.get('redemption', 0) for v in by_month.values())
    return dict(series=series, snapshots=snapshots, capital_cents=capital_now,
                average_monthly_cents=max(0, round(sum(previous) / 6)))


class PlanningApi:
    def planning_snapshot(self):
        try:
            with self._database() as db:
                db.conn.execute('BEGIN')
                result = history(db)
                result['investment_source'] = investidor10.configuration(db)
                scenarios = [dict(r, events=[]) for r in db.rows('SELECT * FROM investment_scenarios ORDER BY id')]
                by_id = {s['id']: s for s in scenarios}
                for row in db.rows('SELECT * FROM investment_scenario_events ORDER BY scenario_id, position'):
                    by_id[row['scenario_id']]['events'].append(dict(row))
                db.conn.rollback()
            result.update(today=date.today().isoformat(), scenarios=scenarios,
                          latest_snapshot=result['snapshots'][-1] if result['snapshots'] else None)
            return result
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_wealth_record(self, payload, item_id=None):
        try:
            values = validate_snapshot(payload)
            with self._database() as db:
                if item_id is None:
                    db.write('INSERT INTO investment_snapshots(day,amount_cents,notes) VALUES (?,?,?) '
                             'ON CONFLICT(day) DO UPDATE SET amount_cents=excluded.amount_cents, notes=excluded.notes',
                             (values['day'], values['amount_cents'], values['notes']))
                else:
                    item_id = self._id(item_id)
                    if not db.rows('SELECT id FROM investment_snapshots WHERE id=?', (item_id,)):
                        raise ValueError('Registro não encontrado. Atualize a tela.')
                    db.write('UPDATE investment_snapshots SET day=?,amount_cents=?,notes=? WHERE id=?',
                             (values['day'], values['amount_cents'], values['notes'], item_id))
            return {'ok': True}
        except sqlite3.IntegrityError:
            return {'ok': False, 'error': 'Já existe um registro nesta data. Edite o registro existente.'}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_scenario(self, payload, item_id=None):
        try:
            values = validate_scenario(payload)
            events = values.pop('events')
            with self._database() as db, db.conn:
                conn = db.conn
                if item_id is None:
                    values['created'] = datetime.now().isoformat(timespec='seconds')
                    item_id = conn.execute(
                        f"INSERT INTO investment_scenarios({','.join(values)}) VALUES ({','.join('?' for _ in values)})",
                        tuple(values.values())).lastrowid
                else:
                    item_id = self._id(item_id)
                    cursor = conn.execute(
                        f"UPDATE investment_scenarios SET {','.join(f'{k}=?' for k in values)} WHERE id=?",
                        (*values.values(), item_id))
                    if cursor.rowcount != 1:
                        raise ValueError('Cenário não encontrado. Atualize a tela.')
                    conn.execute('DELETE FROM investment_scenario_events WHERE scenario_id=?', (item_id,))
                conn.executemany(
                    'INSERT INTO investment_scenario_events(scenario_id,position,title,month,kind,amount_cents,yearly) '
                    'VALUES (?,?,?,?,?,?,?)',
                    [(item_id, i, e['title'], e['month'], e['kind'], e['amount_cents'], e['yearly'])
                     for i, e in enumerate(events)])
            return {'ok': True, 'id': item_id}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def set_scenario_visible(self, item_id, visible):
        try:
            if not isinstance(visible, bool):
                raise ValueError('Opção inválida.')
            with self._database() as db:
                item_id = self._id(item_id)
                if not db.rows('SELECT id FROM investment_scenarios WHERE id=?', (item_id,)):
                    raise ValueError('Cenário não encontrado. Atualize a tela.')
                db.write('UPDATE investment_scenarios SET visible=? WHERE id=?', (int(visible), item_id))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_planning(self, table, item_id):
        try:
            if table not in ('investment_snapshots', 'investment_scenarios'):
                raise ValueError('Tipo de registro inválido.')
            item_id = self._id(item_id)
            with self._database() as db:
                if not db.rows(f'SELECT id FROM {table} WHERE id=?', (item_id,)):
                    raise ValueError('Registro não encontrado. Atualize a tela.')
                db.write(f'DELETE FROM {table} WHERE id=?', (item_id,))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}
