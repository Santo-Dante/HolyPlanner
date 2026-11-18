"""Testes sem conta real: fluxo de sincronização e recuperação de falhas."""

import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from holy_planner.backend import Api
from holy_planner.google_calendar import GoogleError, GoogleSync, event_body, event_days


class FakeGoogle:
    def __init__(self):
        self.events = {}
        self.calls = []
        self.fail_after_insert = False
        self.fail_read = False
        self.external = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, copy.deepcopy(kwargs)))
        if method == "POST":
            body = copy.deepcopy(kwargs["json"])
            key = body["id"]
            if key in self.events:
                raise GoogleError(409)
            self.events[key] = body
            if self.fail_after_insert:
                self.fail_after_insert = False
                raise ConnectionError("Response lost")
            return body
        key = path.rsplit("/", 1)[1]
        if key not in self.events:
            raise GoogleError(404)
        if method == "PATCH":
            self.events[key].update(copy.deepcopy(kwargs["json"]))
            return self.events[key]
        if method == "DELETE":
            del self.events[key]
            return {}
        raise AssertionError(method)

    def pages(self, path, params=None):
        if path == "/users/me/calendarList":
            return [
                {
                    "id": "primary@test",
                    "summary": "Pessoal",
                    "primary": True,
                    "accessRole": "owner",
                    "timeZone": "America/Sao_Paulo",
                }
            ]
        if self.fail_read:
            raise ConnectionError("Offline")
        return copy.deepcopy(list(self.events.values()) + self.external)


class GoogleSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.api = Api(Path(self.temp.name) / "planner.db")
        self.fake = FakeGoogle()
        self.sync = GoogleSync(self.api._database, self.api._path, self.fake)
        with self.api._database() as db:
            self.sync._set(db, "account", "primary@test")
        # Sem auto-worker: os testes chamam sync_once explicitamente.

    def tearDown(self):
        self.temp.cleanup()

    def task(self, due="2026-09-14"):
        return self.api.save("tasks", {"title": "Estudar", "due": due})["id"]

    def test_export_edit_delete_and_no_duplicates(self):
        task = self.task()
        self.sync.sync_once(2026, 9)
        self.assertEqual(len(self.fake.events), 1)
        body = next(iter(self.fake.events.values()))
        self.assertEqual(body["start"], {"date": "2026-09-14"})
        self.assertEqual(body["end"], {"date": "2026-09-15"})
        count = len(self.fake.calls)
        self.sync.sync_once(2026, 9)
        self.assertEqual(len(self.fake.calls), count)
        self.api.save("tasks", {"title": "Novo nome", "due": "2026-09-15"}, task)
        self.sync.sync_once(2026, 9)
        self.assertEqual(len(self.fake.events), 1)
        self.assertEqual(next(iter(self.fake.events.values()))["summary"], "Novo nome")
        self.api.delete("tasks", task)
        self.sync.sync_once(2026, 9)
        self.assertEqual(self.fake.events, {})

    def test_retry_after_server_created_event_but_response_was_lost(self):
        self.task()
        self.fake.fail_after_insert = True
        self.sync.sync_once(2026, 9)
        self.assertTrue(self.sync.status()["error"])
        self.assertEqual(len(self.fake.events), 1)
        self.sync.sync_once(2026, 9)
        self.assertEqual(len(self.fake.events), 1)
        self.assertFalse(self.sync.status()["error"])

    def test_due_removed_and_restored_uses_new_remote_id(self):
        task = self.task()
        self.sync.sync_once(2026, 9)
        old_id = next(iter(self.fake.events))
        self.api.save("tasks", {"title": "Estudar", "due": ""}, task)
        self.sync.sync_once(2026, 9)
        self.assertFalse(self.fake.events)
        self.api.save("tasks", {"title": "Estudar", "due": "2026-09-14"}, task)
        self.sync.sync_once(2026, 9)
        self.assertNotEqual(next(iter(self.fake.events)), old_id)

    def test_import_cache_deletions_and_offline_preservation(self):
        self.fake.external = [
            {
                "id": "outside",
                "summary": "Reunião",
                "start": {"dateTime": "2026-09-15T01:00:00Z"},
                "end": {"dateTime": "2026-09-15T02:00:00Z"},
            }
        ]
        self.sync.sync_once(2026, 9)
        with self.api._database() as db:
            row = db.rows("SELECT * FROM google_cache")[0]
            self.assertEqual(row["day"], "2026-09-14")
            self.assertEqual(row["clock"], "22:00 – 23:00")
        self.fake.fail_read = True
        self.sync.sync_once(2026, 9)
        with self.api._database() as db:
            self.assertEqual(len(db.rows("SELECT * FROM google_cache")), 1)
        self.fake.fail_read = False
        self.fake.external = []
        self.sync.sync_once(2026, 9)
        with self.api._database() as db:
            self.assertEqual(db.rows("SELECT * FROM google_cache"), [])

    def test_recurring_days_and_unplanned_tasks(self):
        body = event_body(
            "routines",
            {
                "title": "Treinar",
                "created": "2026-09-14",
                "days": "1,3",
                "google_uid": "uid",
            },
        )
        self.assertIsNone(body)
        self.assertIsNone(event_body("tasks", {"due": ""}))

    def test_multiday_exclusive_end(self):
        event = {"start": {"date": "2026-09-13"}, "end": {"date": "2026-09-16"}}
        days = event_days(
            event, date(2026, 9, 1), date(2026, 10, 1), ZoneInfo("America/Sao_Paulo")
        )
        self.assertEqual(
            [d for d, _ in days], ["2026-09-13", "2026-09-14", "2026-09-15"]
        )
        timed = {
            "start": {"dateTime": "2026-09-14T20:00:00-03:00"},
            "end": {"dateTime": "2026-09-15T00:00:00-03:00"},
        }
        self.assertEqual(
            len(
                event_days(
                    timed,
                    date(2026, 9, 1),
                    date(2026, 10, 1),
                    ZoneInfo("America/Sao_Paulo"),
                )
            ),
            1,
        )

    def test_reused_sqlite_id_keeps_different_google_identity(self):
        task = self.task()
        self.sync.sync_once(2026, 9)
        old = next(iter(self.fake.events))
        self.api.delete("tasks", task)
        self.task()
        self.sync.sync_once(2026, 9)
        self.assertEqual(len(self.fake.events), 1)
        self.assertNotEqual(next(iter(self.fake.events)), old)

    def test_remote_deleted_event_recreated_after_local_edit(self):
        task = self.task()
        self.sync.sync_once(2026, 9)
        old = next(iter(self.fake.events))
        self.fake.events.clear()
        self.api.save("tasks", {"title": "Revisar", "due": "2026-09-14"}, task)
        self.sync.sync_once(2026, 9)
        self.assertFalse(self.sync.status()["error"])
        self.assertEqual(len(self.fake.events), 1)
        self.assertNotEqual(next(iter(self.fake.events)), old)

    def test_own_export_not_imported_twice(self):
        self.task()
        self.sync.sync_once(2026, 9)
        with self.api._database() as db:
            self.assertEqual(db.rows("SELECT * FROM google_cache"), [])


if __name__ == "__main__":
    unittest.main()
