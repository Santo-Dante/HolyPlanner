"""Testes das regras e persistência; não exigem abrir a interface."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from holy_planner.database import Database, valid_date


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.db"
        self.db = Database(self.path)

    def tearDown(self):
        self.db.conn.close()
        self.temp.cleanup()

    def test_project_delete_preserves_task_and_reopen_persists(self):
        project = self.db.save("projects", {"title": "Projeto"})
        task = self.db.save("tasks", {"title": "Tarefa", "project_id": project})
        self.db.write("DELETE FROM projects WHERE id=?", (project,))
        self.db.conn.close()
        self.db = Database(self.path)
        row = self.db.rows("SELECT * FROM tasks WHERE id=?", (task,))[0]
        self.assertIsNone(row["project_id"])
        self.assertEqual(row["title"], "Tarefa")

    def test_routine_occurrences_are_independent_and_toggleable(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        routine = self.db.save(
            "routines",
            {"title": "Estudar", "days": "0,1,2,3,4,5,6", "created": today.isoformat()},
        )
        self.db.toggle_routine(routine, today)
        self.assertEqual(self.db.routines_on(today)[0]["done"], 1)
        self.assertEqual(self.db.routines_on(tomorrow)[0]["done"], 0)
        self.db.toggle_routine(routine, today)
        self.assertEqual(self.db.routines_on(today)[0]["done"], 0)
        self.assertEqual(self.db.routines_on(today - timedelta(days=1)), [])

    def test_unscheduled_day_rejected(self):
        today = date.today()
        routine = self.db.save(
            "routines",
            {
                "title": "Ler",
                "days": str((today.weekday() + 1) % 7),
                "created": today.isoformat(),
            },
        )
        with self.assertRaises(ValueError):
            self.db.toggle_routine(routine, today)

    def test_backup_has_data(self):
        self.db.save("tasks", {"title": "Persistir"})
        backup = Path(self.temp.name) / "backup.db"
        self.db.backup(backup)
        copy = Database(backup)
        self.assertEqual(copy.rows("SELECT title FROM tasks")[0]["title"], "Persistir")
        self.assertEqual(copy.rows("PRAGMA integrity_check")[0][0], "ok")
        copy.conn.close()
        with self.assertRaises(ValueError):
            self.db.backup(self.path)

    def test_validation_and_parameterized_text(self):
        self.assertEqual(valid_date("29/02/2028"), "2028-02-29")
        with self.assertRaises(ValueError):
            valid_date("31/02/2026")
        with self.assertRaises(ValueError):
            self.db.save("tasks", {"title": "  "})
        with self.assertRaises(ValueError):
            self.db.save("routines", {"title": "Ler", "days": ""})
        title = "Thiago's projeto; DROP TABLE tasks;"
        self.db.save("tasks", {"title": title})
        self.assertEqual(self.db.rows("SELECT title FROM tasks")[0]["title"], title)


if __name__ == "__main__":
    unittest.main()
