import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from holy_planner.backend import Api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.api = Api(Path(self.temp.name) / "planner.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_crud_and_legacy_schema(self):
        p = self.api.save("projects", {"title": "Projeto"})["id"]
        t = self.api.save("tasks", {"title": "Tarefa", "project_id": p})["id"]
        self.api.toggle_task(t)
        self.assertEqual(self.api.snapshot()["projects"][0]["done"], 1)
        self.api.delete("projects", p)
        self.assertIsNone(self.api.snapshot()["tasks"][0]["project_id"])
        self.assertEqual(Api(self.api._path).snapshot()["tasks"][0]["title"], "Tarefa")
        backup = self.api.backup()
        self.assertTrue(backup["ok"])
        self.assertEqual(Api(backup["path"]).snapshot()["tasks"][0]["title"], "Tarefa")

    def test_validation_and_routines(self):
        self.assertFalse(self.api.save("tasks", {"title": "T", "status": "Bad"})["ok"])
        self.assertFalse(
            self.api.save("tasks", {"title": "T", "due": "2026-02-31"})["ok"]
        )
        self.assertFalse(
            self.api.save("tasks", {"title": "T", "project_id": 999})["ok"]
        )
        self.assertFalse(self.api.save("routines", {"title": "R", "days": []})["ok"])
        r = self.api.save("routines", {"title": "R", "days": list(range(7))})["id"]
        self.assertTrue(self.api.toggle_routine(r, date.today().isoformat())["ok"])
        self.assertTrue(self.api.snapshot()["routines"][0]["done"])
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(self.api.toggle_routine(r, future)["ok"])
        self.assertFalse(self.api.snapshot(future)["routines"][0]["done"])

    def test_calendar_month_boundaries_and_completion(self):
        self.api.save("tasks", {"title": "Leap day", "due": "2028-02-29"})
        self.api.save("tasks", {"title": "March", "due": "2028-03-01"})
        month = self.api.calendar_month(2028, 2)
        self.assertEqual(len(month), 29)
        self.assertEqual(month["2028-02-29"]["tasks"], 1)
        self.assertNotIn("2028-03-01", month)
        self.assertEqual(len(self.api.calendar_month(2027, 2)), 28)
        self.assertEqual(len(self.api.calendar_month(2026, 12)), 31)
        today = date.today()
        routine = self.api.save(
            "routines", {"title": "Practice", "days": [today.weekday()]}
        )["id"]
        self.api.toggle_routine(routine, today.isoformat())
        summary = self.api.calendar_month(today.year, today.month)[today.isoformat()]
        self.assertEqual(summary["routines"], 1)
        self.assertEqual(summary["routines_done"], 1)
        with self.assertRaises(ValueError):
            self.api.calendar_month(2026, 13)

    def test_multithreaded_bridge(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(lambda n: self.api.save("tasks", {"title": str(n)}), range(12))
            )
        self.assertTrue(all(r["ok"] for r in results))
        self.assertEqual(len(self.api.snapshot()["tasks"]), 12)


if __name__ == "__main__":
    unittest.main()
