"""Regressões da revisão 2.5; nenhuma chamada de rede."""

import unittest
from unittest.mock import patch
from datetime import date
from tests import test_google_calendar
from holy_planner.google_calendar import GoogleSync
from tests import test_backend
class ReviewApiTests(unittest.TestCase):
    setUp = test_backend.ApiTests.setUp
    tearDown = test_backend.ApiTests.tearDown

    def test_routines_never_schedule_google(self):
        with patch.object(self.api._google, "request_sync") as request:
            result = self.api.save("routines", {"title": "Ler", "days": list(range(7))})
            item = result["id"]
            self.assertTrue(
                self.api.toggle_routine(item, date.today().isoformat())["ok"]
            )
            self.assertTrue(
                self.api.save("routines", {"title": "Ler mais", "days": [0]}, item)[
                    "ok"
                ]
            )
            self.assertTrue(self.api.delete("routines", item)["ok"])
            request.assert_not_called()

    def test_saved_data_survives_sync_start_failure(self):
        with patch.object(
            self.api._google, "request_sync", side_effect=RuntimeError("thread")
        ):
            result = self.api.save("tasks", {"title": "Persistida"})
            self.assertTrue(result["ok"])
            self.assertTrue(result["warning"])
            self.assertEqual(len(self.api.snapshot()["tasks"]), 1)

    def test_reject_invalid_payloads_and_identifiers(self):
        for value in (None, [], {"title": None}, {"title": "T", "notes": "x" * 10001}):
            self.assertFalse(self.api.save("tasks", value)["ok"])
        for value in (True, 1.5, -1, "1.0", 999):
            self.assertFalse(self.api.delete("tasks", value)["ok"])
            self.assertFalse(self.api.toggle_task(value)["ok"])
        for day in (True, 1.5, {}, "7"):
            self.assertFalse(
                self.api.save("routines", {"title": "R", "days": [day]})["ok"]
            )

    def test_month_matches_daily_snapshots(self):
        today = date.today()
        self.api.save("routines", {"title": "R", "days": list(range(7))})
        item = self.api.save("tasks", {"title": "T", "due": today.isoformat()})["id"]
        self.api.toggle_task(item)
        self.api.save("projects", {"title": "P", "due": today.isoformat()})
        for day, counts in self.api.calendar_month(today.year, today.month).items():
            snapshot = self.api.snapshot(day)
            self.assertEqual(
                counts["routines"], sum(r["scheduled"] for r in snapshot["routines"])
            )
            self.assertEqual(
                counts["tasks"], sum(t["due"] == day for t in snapshot["tasks"])
            )
            self.assertEqual(
                counts["projects"], sum(p["due"] == day for p in snapshot["projects"])
            )


class ReviewSyncTests(unittest.TestCase):
    setUp = test_google_calendar.GoogleSyncTests.setUp
    tearDown = test_google_calendar.GoogleSyncTests.tearDown

    def test_new_routines_not_exported(self):
        self.api.save("routines", {"title": "Local", "days": [0, 1]})
        self.sync.sync_once(2026, 9)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.fake.events, {})

    def test_old_routine_links_preserved_after_edit_delete_restart(self):
        item = self.api.save("routines", {"title": "Antiga", "days": [0]})["id"]
        uid = self.api.snapshot()["routines"][0]["google_uid"]
        with self.api._database() as db:
            db.conn.executescript("""
                DROP TABLE google_links;
                CREATE TABLE google_links (
                    calendar_id TEXT, uid TEXT, event_id TEXT,
                    sent_hash TEXT DEFAULT '', removed INTEGER DEFAULT 0,
                    PRIMARY KEY(calendar_id,uid));
            """)
            for key, remote in ((uid, "oldroutine"), ("unknown", "oldunknown")):
                db.write(
                    "INSERT INTO google_links VALUES (?,?,?,'old',0)",
                    ("primary@test", key, remote),
                )
        self.fake.external = [
            {
                "id": "oldroutine_20260914",
                "recurringEventId": "oldroutine",
                "summary": "Antiga",
                "start": {"date": "2026-09-14"},
                "end": {"date": "2026-09-15"},
            }
        ]
        self.sync = GoogleSync(self.api._database, self.api._path, self.fake)
        self.api.save("routines", {"title": "Editada", "days": [1]}, item)
        self.sync.sync_once(2026, 9)
        self.api.delete("routines", item)
        self.sync = GoogleSync(self.api._database, self.api._path, self.fake)
        self.sync.sync_once(2026, 9)
        self.assertEqual(self.fake.calls, [])
        with self.api._database() as db:
            self.assertEqual(db.rows("SELECT * FROM google_cache"), [])
            self.assertEqual(len(db.rows("SELECT * FROM google_links")), 2)


if __name__ == "__main__":
    unittest.main()
