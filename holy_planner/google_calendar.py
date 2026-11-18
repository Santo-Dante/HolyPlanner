"""Google Agenda: OAuth desktop, exportação idempotente e cache mensal offline."""

from __future__ import annotations

from contextlib import nullcontext
import calendar
import hashlib
import json
import threading
import uuid
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]
BASE = "https://www.googleapis.com/calendar/v3"


def event_body(table, row):
    """Itens locais sem horário são eventos de dia inteiro; fim exclusivo."""
    if table not in ("projects", "tasks") or not row.get("due"):
        return None
    start = date.fromisoformat(row["due"])
    title = row["title"]
    if table == "tasks" and row["status"] == "Concluído":
        title = "✓ " + title
    description = row.get("notes", row.get("description", ""))
    body = {
        "summary": title,
        "description": description
        + "\n\nCriado pelo Holy Planner. Edite este item no aplicativo.",
        "start": {"date": start.isoformat()},
        "end": {"date": (start + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {"holy_uid": row["google_uid"]}},
    }
    return body


def event_days(event, first, end, zone):
    """Converte fuso e expande eventos de vários dias, respeitando fim exclusivo."""
    start_value, end_value = event.get("start", {}), event.get("end", {})
    if "date" in start_value:
        start = date.fromisoformat(start_value["date"])
        stop = date.fromisoformat(end_value.get("date", start_value["date"]))
        clock = "Dia inteiro"
    elif "dateTime" in start_value:
        start_dt = datetime.fromisoformat(
            start_value["dateTime"].replace("Z", "+00:00")
        ).astimezone(zone)
        end_dt = datetime.fromisoformat(
            end_value.get("dateTime", start_value["dateTime"]).replace("Z", "+00:00")
        ).astimezone(zone)
        start = start_dt.date()
        stop = (
            (end_dt - timedelta(microseconds=1)).date() + timedelta(days=1)
            if end_dt > start_dt
            else start + timedelta(days=1)
        )
        clock = start_dt.strftime("%H:%M") + " – " + end_dt.strftime("%H:%M")
    else:
        return []
    result = []
    current = max(start, first)
    while current < min(stop, end):
        result.append((current.isoformat(), clock))
        current += timedelta(days=1)
    return result


class GoogleError(Exception):
    def __init__(self, status):
        self.status = status
        messages = {
            401: "Reconecte sua conta Google.",
            403: "Confira a API, as permissões e o acesso à agenda no Google.",
            429: "Limite temporário do Google. Tente sincronizar mais tarde.",
        }
        super().__init__(
            messages.get(
                status, f"Google Agenda indisponível (HTTP {status}). Tente novamente."
            )
        )


class GoogleClient:
    def __init__(self, token_key):
        self.token_key = token_key
        self.session = None

    def authorize(self, credentials_path):
        from google_auth_oauthlib.flow import InstalledAppFlow

        if "installed" not in json.loads(
            Path(credentials_path).read_text(encoding="utf-8")
        ):
            raise ValueError(
                "Use um credentials.json de cliente OAuth do tipo Aplicativo para computador."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            timeout_seconds=180,
            open_browser=True,
            prompt="consent",
            authorization_prompt_message="Autorize o Holy Planner no navegador.",
            success_message="Holy Planner autorizado. Você pode fechar esta aba.",
        )
        self._store(credentials)
        self._session(credentials)

    def _store(self, credentials):
        import keyring

        keyring.set_password(
            "HolyPlanner.GoogleCalendar", self.token_key, credentials.to_json()
        )

    def _session(self, credentials):
        from google.auth.transport.requests import AuthorizedSession

        self.session = AuthorizedSession(credentials)

    def restore(self):
        import keyring
        from google.oauth2.credentials import Credentials

        raw = keyring.get_password("HolyPlanner.GoogleCalendar", self.token_key)
        if not raw:
            raise ValueError("Conecte a conta Google neste computador.")
        self._session(Credentials.from_authorized_user_info(json.loads(raw), SCOPES))

    def forget(self):
        import keyring
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password("HolyPlanner.GoogleCalendar", self.token_key)
        except PasswordDeleteError:
            pass
        if self.session:
            self.session.close()
        self.session = None

    def request(self, method, path, **kwargs):
        if self.session is None:
            self.restore()
        response = self.session.request(method, BASE + path, timeout=25, **kwargs)
        if not response.ok:
            raise GoogleError(response.status_code)
        self._store(self.session.credentials)
        return response.json() if response.content else {}

    def pages(self, path, params=None):
        params = dict(params or {})
        result = []
        while True:
            page = self.request("GET", path, params=params)
            result.extend(page.get("items", []))
            if not page.get("nextPageToken"):
                return result
            params["pageToken"] = page["nextPageToken"]


def calendar_path(calendar_id):
    return "/calendars/" + quote(calendar_id, safe="") + "/events"


class GoogleSync:
    def __init__(self, database, data_file, client=None):
        self._database = database
        self._data_file = Path(data_file)
        self._client = client or GoogleClient(
            hashlib.sha256(str(self._data_file.resolve()).encode()).hexdigest()
        )
        self._guard = threading.RLock()
        self._busy = False
        self._error = ""
        self._wanted = None
        self._revision = 0
        with self._database() as db:
            db.conn.executescript("""
                CREATE TABLE IF NOT EXISTS google_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS google_links (
                    calendar_id TEXT NOT NULL, uid TEXT NOT NULL, event_id TEXT NOT NULL,
                    sent_hash TEXT NOT NULL DEFAULT '', removed INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(calendar_id, uid)
                );
                CREATE TABLE IF NOT EXISTS google_cache (
                    calendar_id TEXT NOT NULL, event_id TEXT NOT NULL, day TEXT NOT NULL,
                    title TEXT NOT NULL, clock TEXT NOT NULL, calendar_name TEXT NOT NULL,
                    PRIMARY KEY(calendar_id,event_id,day)
                );
                CREATE TABLE IF NOT EXISTS google_months (month TEXT PRIMARY KEY, synced TEXT NOT NULL);
            """)
            columns = {r[1] for r in db.rows("PRAGMA table_info(google_links)")}
            if "source_kind" not in columns:
                # Vínculos antigos sem origem identificável são preservados, nunca apagados por palpite.
                db.conn.execute(
                    "ALTER TABLE google_links ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'legacy'"
                )
                for table in ("projects", "tasks", "routines"):
                    db.conn.execute(
                        f"UPDATE google_links SET source_kind=? WHERE uid IN (SELECT google_uid FROM {table})",
                        (table,),
                    )
                db.conn.execute(
                    "DELETE FROM google_cache WHERE event_id IN (SELECT event_id FROM google_links WHERE source_kind IN ('routines','legacy'))"
                )
            db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_google_cache_day ON google_cache(day)"
            )
            db.conn.commit()

    def _meta(self, db, key, default=""):
        rows = db.rows("SELECT value FROM google_meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def _set(self, db, key, value):
        db.write("INSERT OR REPLACE INTO google_meta VALUES (?,?)", (key, value))

    def status(self, db=None):
        with nullcontext(db) if db is not None else self._database() as db:
            return {
                "connected": self._meta(db, "connected") == "1",
                "account": self._meta(db, "account"),
                "timezone": self._meta(db, "timezone", "America/Sao_Paulo"),
                "last_sync": self._meta(db, "last_sync"),
                "busy": self._busy,
                "revision": self._revision,
                "error": self._error,
            }

    def connect(self):
        with self._guard:
            if self._busy:
                return {"ok": False, "error": "Aguarde a operação atual do Google."}
            self._busy = True
        try:
            folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
            path = folder / 'credentials.json'
            if not path.exists():
                raise ValueError(
                    "Coloque credentials.json (OAuth para computador) na pasta do Holy Planner (ao lado de app.py ou do .exe). Veja docs/GOOGLE_AGENDA.md."
                )
            with self._database() as db:
                self._set(db, "connected", "0")
            self._client.authorize(path)
            calendars = self._client.pages("/users/me/calendarList")
            primary = next((c for c in calendars if c.get("primary")), None)
            if not primary or primary.get("accessRole") not in ("owner", "writer"):
                raise ValueError(
                    "Não foi encontrada uma agenda principal com permissão de escrita."
                )
            with self._database() as db:
                previous = self._meta(db, "account")
                if previous != primary["id"]:
                    db.write("DELETE FROM google_cache")
                    db.write("DELETE FROM google_months")
                self._set(db, "account", primary["id"])
                self._set(db, "timezone", primary.get("timeZone", "America/Sao_Paulo"))
                self._set(db, "connected", "1")
            self._error = ""
            self._revision += 1
            return {"ok": True}
        except Exception as exc:
            self._error = self._friendly(exc)
            return {"ok": False, "error": self._error}
        finally:
            self._busy = False

    def disconnect(self):
        with self._guard:
            if self._busy:
                return {
                    "ok": False,
                    "error": "Aguarde a sincronização antes de desconectar.",
                }
            try:
                self._client.forget()
                with self._database() as db:
                    self._set(db, "connected", "0")
                    db.write("DELETE FROM google_cache")
                    db.write("DELETE FROM google_months")
                self._error = ""
                self._revision += 1
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": self._friendly(exc)}

    def request_sync(self, year, month):
        date(int(year), int(month), 1)
        with self._guard:
            if not self.status()["connected"]:
                return {"ok": True, "started": False}
            self._wanted = (int(year), int(month))
            if self._busy:
                return {"ok": True, "started": False}
            self._busy = True
            try:
                threading.Thread(target=self._worker, daemon=True).start()
            except Exception:
                self._busy = False
                self._wanted = None
                raise
            return {"ok": True, "started": True}

    def _worker(self):
        try:
            while True:
                with self._guard:
                    requested = self._wanted
                    self._wanted = None
                if requested:
                    self.sync_once(*requested)
                with self._guard:
                    if not self._wanted:
                        self._busy = False
                        return
        except Exception as exc:
            self._error = self._friendly(exc)
            self._revision += 1
            with self._guard:
                self._busy = False
                self._wanted = None

    @staticmethod
    def _friendly(exc):
        if isinstance(exc, (GoogleError, ValueError)):
            return str(exc)
        if isinstance(exc, ImportError):
            return "Execute instalar_windows.bat novamente para instalar as dependências do Google."
        return "Não foi possível acessar o Google. Confira a internet e as credenciais; tente sincronizar ou reconectar."

    def sync_once(self, year, month):
        """Rede fora da trava SQLite; alterações offline são reconciliadas ao retomar."""
        with self._database() as db:
            target = self._meta(db, "account")
            zone = ZoneInfo(self._meta(db, "timezone", "America/Sao_Paulo"))
            desired = {}
            all_uids = set()
            for table in ("projects", "tasks"):
                for row in db.rows(f"SELECT * FROM {table}"):
                    row = dict(row)
                    all_uids.add(row["google_uid"])
                    body = event_body(table, row)
                    if body:
                        desired[row["google_uid"]] = body
                        db.write(
                            "INSERT OR IGNORE INTO google_links(calendar_id,uid,event_id,source_kind) VALUES (?,?,?,?)",
                            (target, row["google_uid"], uuid.uuid4().hex, table),
                        )
            links = [
                dict(r)
                for r in db.rows(
                    "SELECT * FROM google_links WHERE calendar_id=? AND source_kind IN ('tasks','projects')",
                    (target,),
                )
            ]
        with self._database() as db:
            detached_ids = {
                r["event_id"]
                for r in db.rows(
                    "SELECT event_id FROM google_links WHERE calendar_id=? AND source_kind IN ('routines','legacy')",
                    (target,),
                )
            }
        managed_ids = {link["event_id"] for link in links if link["uid"] in all_uids}
        errors = []
        for link in links:
            body = desired.get(link["uid"])
            digest = (
                hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
                if body
                else ""
            )
            path = calendar_path(target)
            event_id = link["event_id"]
            try:
                if body is None:
                    if link["removed"]:
                        continue
                    try:
                        self._client.request(
                            "DELETE",
                            path + "/" + event_id,
                            params={"sendUpdates": "none"},
                        )
                    except GoogleError as exc:
                        if exc.status not in (404, 410):
                            raise
                    with self._database() as db:
                        db.write(
                            "UPDATE google_links SET removed=1,sent_hash=? WHERE calendar_id=? AND uid=?",
                            ("", target, link["uid"]),
                        )
                    continue
                if link["removed"]:
                    event_id = uuid.uuid4().hex
                    with self._database() as db:
                        db.write(
                            "UPDATE google_links SET event_id=?,removed=0,sent_hash=? WHERE calendar_id=? AND uid=?",
                            (event_id, "", target, link["uid"]),
                        )
                    link["sent_hash"] = ""
                if link["sent_hash"] == digest:
                    continue
                if not link["sent_hash"]:
                    try:
                        self._client.request(
                            "POST",
                            path,
                            json={"id": event_id, **body},
                            params={"sendUpdates": "none"},
                        )
                    except GoogleError as exc:
                        if exc.status != 409:
                            raise
                        # O mesmo ID torna uma repetição após falha de rede idempotente.
                        self._client.request(
                            "PATCH",
                            path + "/" + event_id,
                            json=body,
                            params={"sendUpdates": "none"},
                        )
                else:
                    try:
                        self._client.request(
                            "PATCH",
                            path + "/" + event_id,
                            json=body,
                            params={"sendUpdates": "none"},
                        )
                    except GoogleError as exc:
                        if exc.status not in (404, 410):
                            raise
                        # Um evento removido no Google pode ser recriado após editar no app.
                        event_id = uuid.uuid4().hex
                        with self._database() as db:
                            db.write(
                                "UPDATE google_links SET event_id=?,sent_hash='' WHERE calendar_id=? AND uid=?",
                                (event_id, target, link["uid"]),
                            )
                        self._client.request(
                            "POST",
                            path,
                            json={"id": event_id, **body},
                            params={"sendUpdates": "none"},
                        )
                with self._database() as db:
                    db.write(
                        "UPDATE google_links SET sent_hash=?,removed=0 WHERE calendar_id=? AND uid=?",
                        (digest, target, link["uid"]),
                    )
            except Exception as exc:
                errors.append(self._friendly(exc))
        first = date(year, month, 1)
        end = first + timedelta(days=calendar.monthrange(year, month)[1])
        lower = datetime.combine(first, time.min, zone).isoformat()
        upper = datetime.combine(end, time.min, zone).isoformat()
        calendars = self._client.pages("/users/me/calendarList")
        readable = [
            c for c in calendars if c.get("accessRole") in ("owner", "writer", "reader")
        ]
        for cal in readable:
            try:
                events = self._client.pages(
                    calendar_path(cal["id"]),
                    {
                        "timeMin": lower,
                        "timeMax": upper,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 2500,
                        "timeZone": str(zone),
                    },
                )
                rows = []
                for event in events:
                    if event.get("status") == "cancelled":
                        continue
                    uid = (
                        event.get("extendedProperties", {})
                        .get("private", {})
                        .get("holy_uid")
                    )
                    if cal["id"] == target and (
                        uid in all_uids
                        or event.get("recurringEventId", event["id"])
                        in (managed_ids | detached_ids)
                    ):
                        continue  # Itens locais já aparecem no calendário; evita duplicação.
                    for day, clock in event_days(event, first, end, zone):
                        rows.append(
                            (
                                cal["id"],
                                event["id"],
                                day,
                                event.get("summary", "(Sem título)"),
                                clock,
                                cal.get("summary", "Google"),
                            )
                        )
                with self._database() as db:
                    with db.conn:
                        db.conn.execute(
                            "DELETE FROM google_cache WHERE calendar_id=? AND day>=? AND day<?",
                            (cal["id"], first.isoformat(), end.isoformat()),
                        )
                        db.conn.executemany(
                            "INSERT OR REPLACE INTO google_cache VALUES (?,?,?,?,?,?)",
                            rows,
                        )
            except Exception as exc:
                errors.append(self._friendly(exc))
        if not errors:
            with self._database() as db:
                allowed = {c["id"] for c in readable}
                for row in db.rows("SELECT DISTINCT calendar_id FROM google_cache"):
                    if row["calendar_id"] not in allowed:
                        db.write(
                            "DELETE FROM google_cache WHERE calendar_id=?",
                            (row["calendar_id"],),
                        )
                now = datetime.now(timezone.utc).isoformat()
                self._set(db, "last_sync", now)
                db.write(
                    "INSERT OR REPLACE INTO google_months VALUES (?,?)",
                    (first.strftime("%Y-%m"), now),
                )
        self._error = "; ".join(dict.fromkeys(errors))
        self._revision += 1

    def cached(self, day, db=None):
        with nullcontext(db) if db is not None else self._database() as db:
            if self._meta(db, "connected") != "1":
                return []
            return [
                dict(r)
                for r in db.rows(
                    "SELECT * FROM google_cache WHERE day=? ORDER BY clock,title",
                    (day,),
                )
            ]
