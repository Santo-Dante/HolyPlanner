"""API Python chamada pela interface HTML dentro da janela desktop."""

import calendar
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import RLock
import sqlite3
import webbrowser
from .database import Database, data_path, STATUSES
from .google_calendar import GoogleSync
from . import finance
from . import investidor10
from .productivity import ProductivityApi, bounded_integer
from .workouts import WorkoutsApi
from .investment_plan import PlanningApi
from .life import LifeApi
from . import life
from . import finance_import
import uuid
import re


class Api(ProductivityApi, WorkoutsApi, PlanningApi, LifeApi):
    def __init__(self, path=None, investment_viewer=None, browser_opener=None):
        self._path = Path(path) if path else data_path()
        self._lock = RLock()
        self._investment_viewer = investment_viewer
        self._browser_opener = browser_opener or webbrowser.open
        Database(self._path).conn.close()
        self._google = GoogleSync(self._database, self._path)

    @contextmanager
    def _database(self):
        # pywebview pode chamar métodos em threads diferentes.
        with self._lock:
            db = Database(self._path, initialize=False)
            try:
                yield db
            finally:
                db.conn.close()

    def snapshot(self, day=None):
        selected = date.fromisoformat(day) if day else date.today()
        with self._database() as db:
            projects = db.rows("""SELECT p.*, COUNT(t.id) AS total,
                COALESCE(SUM(t.status='Concluído'),0) AS done
                FROM projects p LEFT JOIN tasks t ON t.project_id=p.id
                GROUP BY p.id ORDER BY p.title""")
            tasks = db.rows("""SELECT t.*, COALESCE(p.title,'Sem projeto') AS project
                FROM tasks t LEFT JOIN projects p ON t.project_id=p.id
                ORDER BY t.due='',t.due,t.id DESC""")
            checks = {r["id"]: bool(r["done"]) for r in db.routines_on(selected)}
            routines = [
                dict(r) for r in db.rows("SELECT * FROM routines ORDER BY title")
            ]
            for r in routines:
                r["scheduled"] = r["id"] in checks
                r["done"] = checks.get(r["id"], False)
            return dict(
                today=date.today().isoformat(),
                day=selected.isoformat(),
                projects=[dict(r) for r in projects],
                tasks=[dict(r) for r in tasks],
                routines=routines,
                routine_week=self._routine_week(db, date.today(), routines),
                google=self._google.status(db=db),
                google_events=self._google.cached(selected.isoformat(), db=db),
                money_today=self._money_today(db),
                journal_today=next((dict(r) for r in db.rows('SELECT * FROM journal WHERE day=?', (date.today().isoformat(),))), None),
            )

    @staticmethod
    def _money_today(db):
        if not db.rows('SELECT 1 FROM finance_transactions LIMIT 1') and not db.rows('SELECT 1 FROM finance_settings WHERE opening_cash_cents<>0'):
            return None
        data = finance.summary(db, date.today().strftime('%Y-%m'))
        return dict(allowance_cents=data['daily_allowance_cents'], days_left=data['days_left'],
                    projected_cents=data['projected_cash_cents'], pending_out_cents=data['pending_out_cents'])

    @staticmethod
    def _routine_week(db, today, routines):
        first = today - timedelta(days=today.weekday())
        last = first + timedelta(days=6)
        checked = {(r['routine_id'], r['day']) for r in db.rows(
            'SELECT routine_id,day FROM checks WHERE day BETWEEN ? AND ?',
            (first.isoformat(), last.isoformat()))}
        result = []
        for number in range(7):
            current = first + timedelta(days=number)
            key = current.isoformat()
            scheduled = [r for r in routines if r['created'] <= key and str(number) in r['days'].split(',')]
            result.append(dict(day=key, total=len(scheduled),
                               done=sum((r['id'], key) in checked for r in scheduled)))
        return result

    def calendar_month(self, year, month):
        """Agrega dados mensais em consultas fixas, sem uma conexão por dia."""
        year, month = int(year), int(month)
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        bounds = (first.isoformat(), last.isoformat())
        with self._database() as db:
            tasks = {
                r["due"]: r
                for r in db.rows(
                    "SELECT due,COUNT(*) AS total,SUM(status='Concluído') AS done FROM tasks WHERE due BETWEEN ? AND ? GROUP BY due",
                    bounds,
                )
            }
            projects = {
                r["due"]: r["total"]
                for r in db.rows(
                    "SELECT due,COUNT(*) AS total FROM projects WHERE due BETWEEN ? AND ? GROUP BY due",
                    bounds,
                )
            }
            routines = db.rows("SELECT * FROM routines WHERE created<=?", (bounds[1],))
            checks = {
                (r["routine_id"], r["day"])
                for r in db.rows(
                    "SELECT * FROM checks WHERE day BETWEEN ? AND ?", bounds
                )
            }
            connected = self._google.status(db=db)["connected"]
            google = (
                {
                    r["day"]: r["total"]
                    for r in db.rows(
                        "SELECT day,COUNT(*) AS total FROM google_cache WHERE day BETWEEN ? AND ? GROUP BY day",
                        bounds,
                    )
                }
                if connected
                else {}
            )
        result = {}
        for number in range(1, last.day + 1):
            day = date(year, month, number)
            key = day.isoformat()
            scheduled = [
                r
                for r in routines
                if r["created"] <= key and str(day.weekday()) in r["days"].split(",")
            ]
            result[key] = {
                "google": google.get(key, 0),
                "projects": projects.get(key, 0),
                "tasks": tasks[key]["total"] if key in tasks else 0,
                "tasks_done": tasks[key]["done"] if key in tasks else 0,
                "routines": len(scheduled),
                "routines_done": sum((r["id"], key) in checks for r in scheduled),
            }
        return result

    @staticmethod
    def _id(value):
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("Identificador inválido.")
        if isinstance(value, str) and not value.isdecimal():
            raise ValueError("Identificador inválido.")
        result = int(value)
        if result < 1:
            raise ValueError("Identificador inválido.")
        return result

    def save(self, table, payload, item_id=None):
        try:
            if table not in ("projects", "tasks", "routines"):
                raise ValueError("Tipo de registro inválido.")
            if not isinstance(payload, dict):
                raise ValueError("Dados do formulário inválidos.")
            if not isinstance(payload.get("title"), str):
                raise ValueError("Preencha o título.")
            if item_id is not None:
                item_id = self._id(item_id)
            title = payload["title"].strip()
            if not title or len(title) > 200:
                raise ValueError("O título deve ter de 1 a 200 caracteres.")
            values = {"title": title}
            if table == "routines":
                raw_days = payload.get("days", [])
                if not isinstance(raw_days, list) or any(
                    type(d) not in (str, int)
                    or str(d) not in tuple(str(i) for i in range(7))
                    for d in raw_days
                ):
                    raise ValueError("Dias da semana inválidos.")
                days = sorted(set(int(d) for d in raw_days))
                if not days or any(d < 0 or d > 6 for d in days):
                    raise ValueError("Escolha pelo menos um dia válido.")
                values["days"] = ",".join(map(str, days))
                if "auto_workout" in payload:
                    values["auto_workout"] = 1 if payload["auto_workout"] in (True, 1, "1", "on") else 0
                if item_id is None:
                    values["created"] = date.today().isoformat()
            else:
                due = str(payload.get("due") or "")
                values["due"] = date.fromisoformat(due).isoformat() if due else ""
                key = "notes" if table == "tasks" else "description"
                note = payload.get(key, "")
                if not isinstance(note, str) or len(note) > 10000:
                    raise ValueError("As notas devem ter no máximo 10.000 caracteres.")
                values[key] = note
                if table == "tasks":
                    if 'estimate_minutes' in payload:
                        values['estimate_minutes'] = bounded_integer(payload['estimate_minutes'] or 0, 0, 1440, 'Estimativa')
                    if 'scheduled_time' in payload:
                        clock = payload['scheduled_time']
                        if not isinstance(clock, str) or (clock and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', clock)):
                            raise ValueError('Horário inválido.')
                        values['scheduled_time'] = clock
                    status = payload.get("status", "A fazer")
                    priority = payload.get("priority", "Média")
                    if status not in STATUSES or priority not in (
                        "Baixa",
                        "Média",
                        "Alta",
                    ):
                        raise ValueError("Status ou prioridade inválidos.")
                    project_id = payload.get("project_id")
                    values.update(
                        status=status,
                        priority=priority,
                        project_id=(
                            self._id(project_id)
                            if project_id not in (None, "")
                            else None
                        ),
                    )
            bill = None
            if table == "tasks" and item_id is None and str(payload.get("finance_amount") or "").strip():
                # Tarefa que também é uma conta: cria um lançamento previsto na data do prazo.
                if not values.get("due"):
                    raise ValueError("Defina o prazo da tarefa para criar o lançamento previsto.")
                bill = dict(title=title, kind="expense", amount=payload["finance_amount"], day=values["due"],
                            category=payload.get("finance_category") or "", status="pending", notes="Criado a partir de uma tarefa.", auto_category=True)
                finance.money_cents(bill["amount"])
            with self._database() as db:
                if item_id is not None and not db.rows(
                    f"SELECT id FROM {table} WHERE id=?", (int(item_id),)
                ):
                    raise ValueError("Registro não encontrado.")
                saved = db.save(
                    table, values, int(item_id) if item_id is not None else None
                )
            warning = self._schedule_google() if table != "routines" else ""
            if bill:
                result = self.save_transaction(bill)
                if not result["ok"]:
                    warning = (warning + " Tarefa salva, mas o lançamento não foi criado: " + result["error"]).strip()
            return {"ok": True, "id": saved, "warning": warning}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    def delete(self, table, item_id):
        try:
            if table not in ("projects", "tasks", "routines"):
                raise ValueError("Tipo inválido.")
            item_id = self._id(item_id)
            with self._database() as db:
                if not db.rows(f"SELECT id FROM {table} WHERE id=?", (item_id,)):
                    raise ValueError("Registro não encontrado. Atualize a tela.")
                db.write(f"DELETE FROM {table} WHERE id=?", (item_id,))
            return {
                "ok": True,
                "warning": self._schedule_google() if table != "routines" else "",
            }
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    def toggle_task(self, item_id):
        try:
            item_id = self._id(item_id)
            with self._database() as db:
                if not db.rows("SELECT id FROM tasks WHERE id=?", (item_id,)):
                    raise ValueError("Tarefa não encontrada. Atualize a tela.")
                db.write(
                    "UPDATE tasks SET status=CASE WHEN status='Concluído' THEN 'A fazer' ELSE 'Concluído' END WHERE id=?",
                    (item_id,),
                )
            return {"ok": True, "warning": self._schedule_google()}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    def toggle_routine(self, item_id, day):
        try:
            item_id = self._id(item_id)
            selected = date.fromisoformat(day)
            if selected > date.today():
                raise ValueError("Não é possível concluir uma rotina futura.")
            with self._database() as db:
                db.toggle_routine(int(item_id), selected)
            return {"ok": True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    def backup(self):
        try:
            folder = self._path.parent / "backups"
            folder.mkdir(exist_ok=True)
            target = folder / f"holy-planner-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
            with self._database() as db:
                db.backup(target)
            return {"ok": True, "path": str(target)}
        except (OSError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    def _schedule_google(self):
        try:
            today = date.today()
            self._google.request_sync(today.year, today.month)
            return ""
        except Exception:
            return "Salvo no computador. Não foi possível iniciar a sincronização; tente Sincronizar novamente."

    def google_connect(self):
        result = self._google.connect()
        if result.get("ok"):
            self._schedule_google()
        return result

    def google_disconnect(self):
        return self._google.disconnect()

    def google_sync(self, year, month):
        return self._google.request_sync(year, month)

    def google_status(self):
        return self._google.status()

    def finance_snapshot(self, month=None):
        try:
            with self._database() as db:
                result = finance.summary(db, month or date.today().strftime('%Y-%m'))
                result['investment_source'] = investidor10.configuration(db)
                return result
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_investment_source(self, payload):
        try:
            values = investidor10.validate_configuration(payload)
            with self._database() as db:
                db.write('UPDATE investment_source SET enabled=?,wallet_url=?,label=? WHERE id=1',
                         (values['enabled'], values['wallet_url'], values['label']))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def open_investidor10(self, section='summary', external=False):
        try:
            if not isinstance(external, bool):
                raise ValueError('Forma de abertura inválida.')
            with self._database() as db:
                config = investidor10.configuration(db)
            if not config['enabled']:
                raise ValueError('Cole o link público da sua carteira em Finanças → Investimentos → Configurar Investidor10.')
            url = investidor10.section_url(config['wallet_url'], section)
            if external:
                if not self._browser_opener(url, new=2):
                    return {'ok': False, 'error': 'Não foi possível abrir o navegador. Copie o link da carteira.'}
            else:
                if self._investment_viewer is None:
                    return {'ok': False, 'error': 'Abra pelo aplicativo desktop ou use Abrir no navegador.'}
                self._investment_viewer(url)
            return {'ok': True, 'url': url, 'mode': 'browser' if external else 'application'}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}
        except Exception:
            return {'ok': False, 'error': 'Não foi possível abrir a carteira. Tente Abrir no navegador ou confira o link nas configurações.'}

    def save_transaction(self, payload, item_id=None):
        try:
            if isinstance(payload, dict) and payload.get('auto_category') is True and not str(payload.get('category') or '').strip():
                # Captura rápida e importação: sugere a categoria pelo histórico e por palavras-chave.
                with self._database() as db:
                    payload = {**payload, 'category': finance_import.suggest_category(self._category_history(db), payload.get('title', ''), payload.get('kind'))}
            values = finance.validate_transaction(payload)
            repeat = 1
            scope = payload.get('scope', 'one')
            if scope not in ('one', 'future'):
                raise ValueError('Escolha se a alteração vale só para este lançamento ou também para os próximos.')
            if item_id is not None:
                item_id = self._id(item_id)
            elif payload.get('repeat_months') not in (None, '', 0, '0', '1', 1):
                repeat = bounded_integer(payload.get('repeat_months'), 1, 60, 'Repetir por (meses)')
            with self._database() as db:
                names = [r['category'] for r in db.rows('SELECT category FROM finance_transactions UNION SELECT category FROM finance_budgets')]
                values['category'] = finance.canonical_name(values['category'], [*finance.CATEGORIES, *names])
                if values['asset']:
                    values['asset'] = finance.canonical_name(values['asset'], [r['asset'] for r in db.rows("SELECT DISTINCT asset FROM finance_transactions WHERE asset<>''")])
                if item_id is None:
                    values['series'] = uuid.uuid4().hex if repeat > 1 else ''
                    columns = ','.join(values)
                    first_day = date.fromisoformat(values['day'])
                    with db.conn:
                        for offset in range(repeat):
                            # Repetições mensais mantêm o dia, limitado ao fim de meses mais curtos.
                            index = first_day.year * 12 + first_day.month - 1 + offset
                            year, month = divmod(index, 12)
                            day = date(year, month + 1, min(first_day.day, calendar.monthrange(year, month + 1)[1]))
                            if day.year > 2100:
                                raise ValueError('As repetições ultrapassam o ano 2100.')
                            row = {**values, 'day': day.isoformat(),
                                   'status': values['status'] if day <= date.today() else 'pending'}
                            new_id = db.conn.execute(f"INSERT INTO finance_transactions ({columns}) VALUES ({','.join('?' for _ in row)})", tuple(row.values())).lastrowid
                            item_id = item_id or new_id
                    updated = repeat
                else:
                    current = db.rows('SELECT day,series FROM finance_transactions WHERE id=?', (item_id,))
                    if not current:
                        raise ValueError('Lançamento não encontrado. Atualize a tela.')
                    with db.conn:
                        db.conn.execute(f"UPDATE finance_transactions SET {','.join(f'{k}=?' for k in values)} WHERE id=?", (*values.values(), item_id))
                        updated = 1
                        if scope == 'future' and current[0]['series']:
                            # Os próximos da série recebem os mesmos dados; datas e situações são mantidas.
                            shared = {k: values[k] for k in ('title', 'kind', 'amount_cents', 'category', 'account', 'asset', 'notes')}
                            cursor = db.conn.execute(f"UPDATE finance_transactions SET {','.join(f'{k}=?' for k in shared)} WHERE series=? AND day>? AND id<>?",
                                                     (*shared.values(), current[0]['series'], current[0]['day'], item_id))
                            updated += cursor.rowcount
            return {'ok': True, 'id': item_id, 'count': updated}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    @staticmethod
    def _category_history(db):
        return [(r['title'], r['category'], r['kind']) for r in db.rows('SELECT title,category,kind FROM finance_transactions ORDER BY id DESC LIMIT 3000')]

    def delete_transaction(self, item_id, scope='one'):
        try:
            if scope not in ('one', 'future'):
                raise ValueError('Opção de exclusão inválida.')
            item_id = self._id(item_id)
            with self._database() as db, db.conn:
                current = db.rows('SELECT day,series FROM finance_transactions WHERE id=?', (item_id,))
                if not current:
                    raise ValueError('Lançamento não encontrado. Atualize a tela.')
                count = db.conn.execute('DELETE FROM finance_transactions WHERE id=?', (item_id,)).rowcount
                if scope == 'future' and current[0]['series']:
                    count += db.conn.execute('DELETE FROM finance_transactions WHERE series=? AND day>?', (current[0]['series'], current[0]['day'])).rowcount
            return {'ok': True, 'count': count}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def copy_budgets(self, month):
        """Copia para o mês os limites do mês anterior que ainda não existem nele."""
        try:
            finance.month_bounds(month)
            year, number = map(int, month.split('-'))
            previous = f'{year - (number == 1):04d}-{(number - 2) % 12 + 1:02d}'
            with self._database() as db:
                cursor = db.conn.execute('INSERT OR IGNORE INTO finance_budgets(month,category,amount_cents) '
                                         'SELECT ?,category,amount_cents FROM finance_budgets WHERE month=?', (month, previous))
                db.conn.commit()
            return {'ok': True, 'count': cursor.rowcount, 'from': previous}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def import_preview(self, text, filename='', invert=False):
        """Lê um extrato e devolve as linhas com tipo, categoria sugerida e possíveis duplicados."""
        try:
            if not isinstance(filename, str) or not isinstance(invert, bool):
                raise ValueError('Arquivo inválido.')
            rows = finance_import.parse_statement(text, filename)
            today = date.today()
            with self._database() as db:
                history = self._category_history(db)
                keys = {r[0] for r in db.rows("SELECT import_key FROM finance_transactions WHERE import_key<>''")}
                existing = {(r['day'], r['amount_cents'], r['kind']) for r in db.rows('SELECT day,amount_cents,kind FROM finance_transactions')}
            result = []
            for row in rows:
                cents = -row['amount'] if invert else row['amount']
                kind = 'income' if cents > 0 else 'expense'
                key = finance_import.import_key(row['day'], row['amount'], row['title'], row['ref'])
                amount = abs(cents)
                if amount > finance.MAX_CENTS or not 1900 <= row['day'].year <= 2100:
                    continue
                result.append(dict(key=key, day=row['day'].isoformat(), title=row['title'][:200], amount_cents=amount, kind=kind,
                                   category=finance_import.suggest_category(history, row['title'], kind),
                                   duplicate=key in keys or (row['day'].isoformat(), amount, kind) in existing,
                                   future=row['day'] > today))
            result.sort(key=lambda r: r['day'], reverse=True)
            return {'ok': True, 'rows': result, 'count': len(result), 'duplicates': sum(r['duplicate'] for r in result)}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def import_commit(self, rows, account=''):
        """Grava as linhas escolhidas. Linhas já importadas (mesma chave) são ignoradas."""
        try:
            if not isinstance(rows, list) or not rows or len(rows) > finance_import.MAX_ROWS:
                raise ValueError('Escolha os lançamentos que deseja importar.')
            account = finance.text_field({'account': account}, 'account', 80)
            prepared = []
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('key'), str) or not re.fullmatch(r'[0-9a-f]{24}', row['key']):
                    raise ValueError('Linha de importação inválida.')
                day = date.fromisoformat(str(row.get('day')))
                values = finance.validate_transaction(dict(title=row.get('title') or 'Lançamento importado', kind=row.get('kind'),
                    amount=f"{int(row.get('amount_cents', 0)) // 100}.{int(row.get('amount_cents', 0)) % 100:02d}", day=day.isoformat(),
                    category=row.get('category') or 'Outros', account=account, status='paid' if day <= date.today() else 'pending'))
                if values['kind'] not in ('income', 'expense'):
                    raise ValueError('A importação aceita entradas e saídas.')
                values['import_key'] = row['key']
                prepared.append(values)
            added = 0
            with self._database() as db, db.conn:
                names = [r['category'] for r in db.rows('SELECT category FROM finance_transactions UNION SELECT category FROM finance_budgets')]
                keys = {r[0] for r in db.rows("SELECT import_key FROM finance_transactions WHERE import_key<>''")}
                for values in prepared:
                    if values['import_key'] in keys:
                        continue
                    values['category'] = finance.canonical_name(values['category'], [*finance.CATEGORIES, *names])
                    db.conn.execute(f"INSERT INTO finance_transactions ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
                    keys.add(values['import_key'])
                    added += 1
            return {'ok': True, 'count': added, 'skipped': len(prepared) - added}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_finance(self, table, item_id):
        try:
            if table not in ('finance_transactions', 'finance_budgets'):
                raise ValueError('Tipo de registro inválido.')
            item_id = self._id(item_id)
            with self._database() as db:
                if not db.rows(f'SELECT id FROM {table} WHERE id=?', (item_id,)):
                    raise ValueError('Registro não encontrado. Atualize a tela.')
                db.write(f'DELETE FROM {table} WHERE id=?', (item_id,))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def toggle_transaction(self, item_id):
        try:
            item_id = self._id(item_id)
            with self._database() as db:
                rows = db.rows('SELECT * FROM finance_transactions WHERE id=?', (item_id,))
                if not rows:
                    raise ValueError('Lançamento não encontrado. Atualize a tela.')
                row = rows[0]
                if row['status'] == 'pending' and row['day'] > date.today().isoformat():
                    raise ValueError('Edite a data para a data real do pagamento antes de efetivar.')
                status = 'pending' if row['status'] == 'paid' else 'paid'
                db.write('UPDATE finance_transactions SET status=? WHERE id=?', (status, item_id))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_budget(self, payload, item_id=None):
        try:
            if not isinstance(payload, dict):
                raise ValueError('Dados do limite inválidos.')
            month = payload.get('month')
            finance.month_bounds(month)
            category = finance.text_field(payload, 'category', 80, True)
            amount = finance.money_cents(payload.get('amount'))
            with self._database() as db:
                names = [r['category'] for r in db.rows('SELECT category FROM finance_transactions UNION SELECT category FROM finance_budgets')]
                category = finance.canonical_name(category, [*finance.CATEGORIES, *names])
                if item_id is None:
                    db.write('INSERT INTO finance_budgets(month,category,amount_cents) VALUES (?,?,?) '
                             'ON CONFLICT(month,category) DO UPDATE SET amount_cents=excluded.amount_cents', (month, category, amount))
                else:
                    item_id = self._id(item_id)
                    if not db.rows('SELECT id FROM finance_budgets WHERE id=?', (item_id,)):
                        raise ValueError('Limite não encontrado.')
                    db.write('UPDATE finance_budgets SET month=?,category=?,amount_cents=? WHERE id=?', (month, category, amount, item_id))
            return {'ok': True}
        except sqlite3.IntegrityError:
            return {'ok': False, 'error': 'Já existe um limite para essa categoria no mês. Edite o limite existente.'}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def save_finance_settings(self, payload):
        try:
            if not isinstance(payload, dict):
                raise ValueError('Dados dos saldos inválidos.')
            cash = finance.money_cents(payload.get('opening_cash'), positive=False, signed=True)
            invested = finance.money_cents(payload.get('opening_invested'), positive=False)
            with self._database() as db:
                db.write('UPDATE finance_settings SET opening_cash_cents=?,opening_invested_cents=? WHERE id=1', (cash, invested))
            return {'ok': True}
        except (ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}

    def export_finances(self, month, filters=None):
        try:
            if filters is not None and not isinstance(filters, dict):
                raise ValueError('Filtros inválidos.')
            filters = filters or {}
            with self._database() as db:
                rows = finance.summary(db, month)['transactions']
            query = str(filters.get('query', '')).casefold()
            for field in ('kind', 'status', 'category'):
                value = filters.get(field)
                if value:
                    rows = [r for r in rows if r[field] == value]
            rows = [r for r in rows if query in ' '.join(r[k] for k in ('title','category','account','asset','notes')).casefold()]
            folder = self._path.parent / 'exports'
            folder.mkdir(exist_ok=True)
            target = folder / f'financas-{month}-{datetime.now():%Y%m%d-%H%M%S-%f}.csv'
            target.write_text(finance.export_csv(rows), encoding='utf-8-sig', newline='')
            return {'ok': True, 'path': str(target), 'count': len(rows)}
        except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': str(exc)}
