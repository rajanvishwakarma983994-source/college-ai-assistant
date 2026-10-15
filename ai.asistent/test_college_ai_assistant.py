import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from college_ai_assistant import StudyTask, TaskStore, recommend_next_task


class TaskStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp_dir.name) / "planner.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_list_complete_and_delete_task(self) -> None:
        due_at = datetime(2026, 10, 15, 9, 30)
        task_id = self.store.add_task("Read chapter", "Biology", due_at, "High", 45)

        tasks = self.store.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, task_id)
        self.assertEqual(tasks[0].due_at, due_at)
        self.assertEqual(tasks[0].estimated_minutes, 45)

        self.store.complete_task(task_id)
        self.assertEqual(self.store.list_tasks(), [])
        self.assertTrue(self.store.list_tasks(include_completed=True)[0].completed)

        self.store.delete_task(task_id)
        self.assertEqual(self.store.list_tasks(include_completed=True), [])

    def test_due_reminder_is_returned_only_once(self) -> None:
        now = datetime(2026, 10, 15, 10, 0)
        self.store.add_task("Submit essay", "", now - timedelta(minutes=1), "Medium", 30)

        self.assertEqual(self.store.take_due_reminders(now), ["Submit essay"])
        self.assertEqual(self.store.take_due_reminders(now), [])

    def test_completed_task_does_not_trigger_reminder(self) -> None:
        now = datetime(2026, 10, 15, 10, 0)
        task_id = self.store.add_task("Review notes", "", now, "Low", 20)
        self.store.complete_task(task_id)

        self.assertEqual(self.store.take_due_reminders(now), [])

    def test_rejects_invalid_priority_and_duration(self) -> None:
        due_at = datetime(2026, 10, 15, 9, 30)
        with self.assertRaises(ValueError):
            self.store.add_task("Study", "", due_at, "Urgent", 30)
        with self.assertRaises(ValueError):
            self.store.add_task("Study", "", due_at, "Low", 0)


class RecommendationTests(unittest.TestCase):
    def test_recommends_overdue_task_first(self) -> None:
        now = datetime(2026, 10, 15, 10, 0)
        tasks = [
            StudyTask(1, "Later exam", "Math", now + timedelta(days=2), "High", 30, False),
            StudyTask(2, "Overdue quiz", "History", now - timedelta(hours=1), "Low", 20, False),
        ]

        recommendation = recommend_next_task(tasks, now)

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation[0].title, "Overdue quiz")
        self.assertIn("overdue", recommendation[1])

    def test_no_recommendation_without_open_tasks(self) -> None:
        now = datetime(2026, 10, 15, 10, 0)
        task = StudyTask(1, "Done", "", now, "High", 20, True)

        self.assertIsNone(recommend_next_task([task], now))


if __name__ == "__main__":
    unittest.main()
