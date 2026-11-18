"""Persistência SQLite compatível com o Holy Planner 1.0."""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

STATUSES = ("A fazer", "Em andamento", "Concluído")
DAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def data_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    folder = base / "HolyPlanner"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "planner.db"


def valid_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise ValueError("Informe uma data válida no formato DD/MM/AAAA.") from exc


def show_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y") if value else "—"


class Database:
    def __init__(self, path: Path, initialize: bool = True):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if initialize:
            try:
                self._initialize_schema()
            except Exception:
                self.conn.close()
                raise

    def _initialize_schema(self):
        """Executa migrações uma vez na inicialização, não em cada consulta."""
        existing = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "tasks" in existing and "finance_transactions" not in existing:
            folder = self.path.parent / "backups"
            folder.mkdir(exist_ok=True)
            self.backup(folder / f"antes-financas-{datetime.now():%Y%m%d-%H%M%S-%f}.db")
        elif 'tasks' in existing and 'goals' not in existing:
            folder = self.path.parent / 'backups'
            folder.mkdir(exist_ok=True)
            self.backup(folder / f'antes-produtividade-{datetime.now():%Y%m%d-%H%M%S-%f}.db')
        elif 'tasks' in existing and 'workout_sessions' not in existing:
            folder = self.path.parent / 'backups'
            folder.mkdir(exist_ok=True)
            self.backup(folder / f'antes-treinos-{datetime.now():%Y%m%d-%H%M%S-%f}.db')
        elif 'tasks' in existing and 'investment_scenarios' not in existing:
            folder = self.path.parent / 'backups'
            folder.mkdir(exist_ok=True)
            self.backup(folder / f'antes-planejamento-{datetime.now():%Y%m%d-%H%M%S-%f}.db')
        elif 'tasks' in existing and 'journal' not in existing:
            folder = self.path.parent / 'backups'
            folder.mkdir(exist_ok=True)
            self.backup(folder / f'antes-5.0-{datetime.now():%Y%m%d-%H%M%S-%f}.db')
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                due TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'Média',
                status TEXT NOT NULL DEFAULT 'A fazer', notes TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, days TEXT NOT NULL,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
                day TEXT NOT NULL, PRIMARY KEY (routine_id, day)
            );
        """)
        for table in ("projects", "tasks", "routines"):
            columns = {
                row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")
            }
            if "google_uid" not in columns:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN google_uid TEXT NOT NULL DEFAULT ''"
                )
            for row in self.conn.execute(
                f"SELECT id FROM {table} WHERE google_uid='' "
            ).fetchall():
                self.conn.execute(
                    f"UPDATE {table} SET google_uid=? WHERE id=?",
                    (uuid.uuid4().hex, row[0]),
                )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_due ON projects(due)"
        )
        self.conn.commit()
        from .finance import initialize_schema
        initialize_schema(self.conn)
        from .investidor10 import initialize_schema as initialize_investment_source
        initialize_investment_source(self.conn)
        from .productivity import initialize_schema as initialize_productivity
        initialize_productivity(self.conn)
        from .workouts import initialize_schema as initialize_workouts
        initialize_workouts(self.conn)
        from .investment_plan import initialize_schema as initialize_planning
        initialize_planning(self.conn)
        from .life import initialize_schema as initialize_life
        initialize_life(self.conn)

    def rows(self, sql, args=()):
        return self.conn.execute(sql, args).fetchall()

    def write(self, sql, args=()):
        with self.conn:
            return self.conn.execute(sql, args).lastrowid

    def save(self, table, values, item_id=None):
        allowed = {
            "projects": {"title", "description", "due"},
            "tasks": {"title", "project_id", "due", "priority", "status", "notes", "estimate_minutes", "scheduled_time"},
            "routines": {"title", "days", "created", "auto_workout"},
        }
        if table not in allowed or not set(values) <= allowed[table]:
            raise ValueError("Campos inválidos.")
        if not values.get("title", "").strip():
            raise ValueError("Preencha o título.")
        if table == "routines" and not values.get("days"):
            raise ValueError("Escolha pelo menos um dia da semana.")
        if item_id is None:
            values = {**values, "google_uid": uuid.uuid4().hex}
            columns = ",".join(values)
            placeholders = ",".join("?" for _ in values)
            return self.write(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
        sets = ",".join(f"{key}=?" for key in values)
        self.write(f"UPDATE {table} SET {sets} WHERE id=?", (*values.values(), item_id))
        return item_id

    def routines_on(self, day: date):
        items = self.rows(
            """SELECT r.*, EXISTS(SELECT 1 FROM checks c
            WHERE c.routine_id=r.id AND c.day=?) AS done FROM routines r
            WHERE r.created<=? ORDER BY r.title COLLATE NOCASE""",
            (day.isoformat(), day.isoformat()),
        )
        return [r for r in items if str(day.weekday()) in r["days"].split(",")]

    def toggle_routine(self, item_id, day: date):
        if item_id not in [r["id"] for r in self.routines_on(day)]:
            raise ValueError("Essa rotina não está programada para a data selecionada.")
        key = (item_id, day.isoformat())
        if self.rows("SELECT 1 FROM checks WHERE routine_id=? AND day=?", key):
            self.write("DELETE FROM checks WHERE routine_id=? AND day=?", key)
        else:
            self.write("INSERT INTO checks VALUES (?,?)", key)

    def backup(self, target):
        if Path(target).resolve() == self.path.resolve():
            raise ValueError("Escolha um arquivo diferente do banco em uso.")
        with closing(sqlite3.connect(target)) as destination:
            self.conn.backup(destination)
