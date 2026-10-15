from __future__ import annotations

import sqlite3
import tkinter as tk
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


DATETIME_FORMAT = "%Y-%m-%d %H:%M"
PRIORITIES = ("Low", "Medium", "High")


@dataclass(frozen=True)
class StudyTask:
    id: int
    title: str
    course: str
    due_at: datetime
    priority: str
    estimated_minutes: int
    completed: bool


class TaskStore:
    def __init__(self, database_path: Path | None = None) -> None:
        if database_path is None:
            data_dir = Path.home() / ".college_ai_assistant"
            data_dir.mkdir(parents=True, exist_ok=True)
            database_path = data_dir / "planner.sqlite3"
        else:
            database_path.parent.mkdir(parents=True, exist_ok=True)

        self.database_path = database_path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    course TEXT NOT NULL DEFAULT '',
                    due_at TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    reminded INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def add_task(
        self,
        title: str,
        course: str,
        due_at: datetime,
        priority: str,
        estimated_minutes: int,
    ) -> int:
        if priority not in PRIORITIES:
            raise ValueError("Choose Low, Medium, or High priority.")
        if estimated_minutes <= 0:
            raise ValueError("Estimated study time must be greater than zero.")

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (title, course, due_at, priority, estimated_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    course.strip(),
                    due_at.strftime(DATETIME_FORMAT),
                    priority,
                    estimated_minutes,
                ),
            )
            return int(cursor.lastrowid)

    def list_tasks(self, include_completed: bool = False) -> list[StudyTask]:
        query = """
            SELECT id, title, course, due_at, priority, estimated_minutes, completed
            FROM tasks
        """
        if not include_completed:
            query += " WHERE completed = 0"
        query += " ORDER BY completed ASC, due_at ASC, id ASC"

        with closing(self._connect()) as connection, connection:
            rows = connection.execute(query).fetchall()
        return [
            StudyTask(
                id=row[0],
                title=row[1],
                course=row[2],
                due_at=datetime.strptime(row[3], DATETIME_FORMAT),
                priority=row[4],
                estimated_minutes=row[5],
                completed=bool(row[6]),
            )
            for row in rows
        ]

    def complete_task(self, task_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,)
            )

    def delete_task(self, task_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def take_due_reminders(self, now: datetime) -> list[str]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT id, title FROM tasks
                WHERE completed = 0 AND reminded = 0 AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now.strftime(DATETIME_FORMAT),),
            ).fetchall()
            connection.executemany(
                "UPDATE tasks SET reminded = 1 WHERE id = ?",
                [(row[0],) for row in rows],
            )
        return [row[1] for row in rows]


def recommend_next_task(
    tasks: list[StudyTask], now: datetime
) -> tuple[StudyTask, str] | None:
    open_tasks = [task for task in tasks if not task.completed]
    if not open_tasks:
        return None

    priority_weight = {"Low": 0, "Medium": 2, "High": 4}

    def score(task: StudyTask) -> float:
        hours_until_due = (task.due_at - now).total_seconds() / 3600
        urgency = 100 if hours_until_due <= 0 else 24 / max(hours_until_due, 1)
        return priority_weight[task.priority] + urgency

    task = max(open_tasks, key=score)
    hours_until_due = (task.due_at - now).total_seconds() / 3600
    if hours_until_due <= 0:
        reason = "It is overdue, so it should be your first priority."
    elif hours_until_due <= 24:
        reason = "Its deadline is within the next 24 hours."
    elif task.priority == "High":
        reason = "It has high priority."
    else:
        reason = "It is the most time-sensitive open task."
    return task, reason


class CollegeAssistantApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("College AI Assistant - Study Planner")
        self.root.geometry("920x600")
        self.root.minsize(760, 480)
        self.store = TaskStore()

        self._build_ui()
        self.refresh_tasks()
        self.root.after(1000, self.check_reminders)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=18)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="College AI Assistant",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            container,
            text="Your private study planner and deadline reminders",
        ).pack(anchor=tk.W, pady=(2, 14))

        form = ttk.LabelFrame(container, text="Add a study task", padding=10)
        form.pack(fill=tk.X, pady=(0, 12))
        self.title_var = tk.StringVar()
        self.course_var = tk.StringVar()
        self.due_var = tk.StringVar(
            value=(datetime.now() + timedelta(hours=1)).strftime(DATETIME_FORMAT)
        )
        self.priority_var = tk.StringVar(value="Medium")
        self.minutes_var = tk.StringVar(value="30")

        fields = (
            ("Task", self.title_var, 24),
            ("Course", self.course_var, 16),
            ("Due (YYYY-MM-DD HH:MM)", self.due_var, 20),
        )
        for column, (label, variable, width) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky=tk.W, padx=4)
            ttk.Entry(form, textvariable=variable, width=width).grid(
                row=1, column=column, sticky=tk.EW, padx=4
            )

        ttk.Label(form, text="Priority").grid(row=0, column=3, sticky=tk.W, padx=4)
        ttk.Combobox(
            form,
            textvariable=self.priority_var,
            values=PRIORITIES,
            state="readonly",
            width=9,
        ).grid(row=1, column=3, sticky=tk.EW, padx=4)
        ttk.Label(form, text="Minutes").grid(row=0, column=4, sticky=tk.W, padx=4)
        ttk.Entry(form, textvariable=self.minutes_var, width=8).grid(
            row=1, column=4, sticky=tk.EW, padx=4
        )
        ttk.Button(form, text="Add task", command=self.add_task).grid(
            row=1, column=5, padx=(8, 4)
        )
        form.columnconfigure(0, weight=2)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=2)

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            actions, text="Suggest next task", command=self.suggest_next_task
        ).pack(side=tk.LEFT)
        ttk.Button(actions, text="Mark complete", command=self.complete_selected).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(actions, text="Delete", command=self.delete_selected).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="Refresh", command=self.refresh_tasks).pack(
            side=tk.RIGHT
        )

        columns = ("task", "course", "due", "priority", "minutes", "status")
        self.task_tree = ttk.Treeview(
            container, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "task": ("Task", 245),
            "course": ("Course", 125),
            "due": ("Due", 145),
            "priority": ("Priority", 85),
            "minutes": ("Minutes", 75),
            "status": ("Status", 90),
        }
        for column, (heading, width) in headings.items():
            self.task_tree.heading(column, text=heading)
            self.task_tree.column(column, width=width, anchor=tk.W)
        self.task_tree.pack(fill=tk.BOTH, expand=True)

        self.summary_var = tk.StringVar()
        ttk.Label(container, textvariable=self.summary_var).pack(
            anchor=tk.W, pady=(8, 0)
        )

    def add_task(self) -> None:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Missing task", "Enter a task title.", parent=self.root)
            return
        try:
            due_at = datetime.strptime(self.due_var.get().strip(), DATETIME_FORMAT)
            estimated_minutes = int(self.minutes_var.get())
            self.store.add_task(
                title,
                self.course_var.get(),
                due_at,
                self.priority_var.get(),
                estimated_minutes,
            )
        except ValueError as error:
            messagebox.showerror(
                "Check task details",
                f"Enter the due date as YYYY-MM-DD HH:MM and a positive number of minutes.\n\n{error}",
                parent=self.root,
            )
            return
        except sqlite3.Error as error:
            messagebox.showerror(
                "Could not save task", str(error), parent=self.root
            )
            return

        self.title_var.set("")
        self.course_var.set("")
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        try:
            tasks = self.store.list_tasks(include_completed=True)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Could not load tasks", str(error), parent=self.root
            )
            return

        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        now = datetime.now()
        for task in tasks:
            status = "Complete" if task.completed else (
                "Overdue" if task.due_at <= now else "Open"
            )
            self.task_tree.insert(
                "",
                tk.END,
                iid=str(task.id),
                values=(
                    task.title,
                    task.course or "—",
                    task.due_at.strftime(DATETIME_FORMAT),
                    task.priority,
                    task.estimated_minutes,
                    status,
                ),
            )

        open_tasks = [task for task in tasks if not task.completed]
        overdue_count = sum(task.due_at <= now for task in open_tasks)
        upcoming_count = sum(
            now < task.due_at <= now + timedelta(days=7) for task in open_tasks
        )
        self.summary_var.set(
            f"{len(open_tasks)} open  ·  {overdue_count} overdue  ·  "
            f"{upcoming_count} due in the next 7 days"
        )

    def selected_task_id(self) -> int | None:
        selection = self.task_tree.selection()
        return int(selection[0]) if selection else None

    def complete_selected(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            messagebox.showinfo("Select a task", "Choose a task first.", parent=self.root)
            return
        try:
            self.store.complete_task(task_id)
        except sqlite3.Error as error:
            messagebox.showerror(
                "Could not update task", str(error), parent=self.root
            )
            return
        self.refresh_tasks()

    def delete_selected(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            messagebox.showinfo("Select a task", "Choose a task first.", parent=self.root)
            return
        if not messagebox.askyesno(
            "Delete task", "Delete the selected task?", parent=self.root
        ):
            return
        try:
            self.store.delete_task(task_id)
        except sqlite3.Error as error:
            messagebox.showerror(
                "Could not delete task", str(error), parent=self.root
            )
            return
        self.refresh_tasks()

    def suggest_next_task(self) -> None:
        try:
            recommendation = recommend_next_task(
                self.store.list_tasks(), datetime.now()
            )
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror(
                "Could not make a suggestion", str(error), parent=self.root
            )
            return
        if recommendation is None:
            messagebox.showinfo(
                "Study suggestion", "Add an open task and I can help you prioritize it.",
                parent=self.root,
            )
            return
        task, reason = recommendation
        messagebox.showinfo(
            "Your next study task",
            f"{task.title}"
            f"{f' ({task.course})' if task.course else ''}\n\n"
            f"Suggested study time: {task.estimated_minutes} minutes.\n{reason}",
            parent=self.root,
        )

    def check_reminders(self) -> None:
        try:
            due_titles = self.store.take_due_reminders(datetime.now())
        except sqlite3.Error as error:
            messagebox.showerror(
                "Reminder error", str(error), parent=self.root
            )
            self.root.after(60_000, self.check_reminders)
            return
        if due_titles:
            self.show_reminder(due_titles)
            self.refresh_tasks()
        self.root.after(15_000, self.check_reminders)

    def show_reminder(self, titles: list[str]) -> None:
        notice = tk.Toplevel(self.root)
        notice.title("Study reminder")
        notice.attributes("-topmost", True)
        notice.resizable(False, False)
        frame = ttk.Frame(notice, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame, text="A study task is due", font=("Segoe UI", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 6))
        ttk.Label(frame, text="\n".join(f"• {title}" for title in titles)).pack(
            anchor=tk.W
        )
        ttk.Button(frame, text="Dismiss", command=notice.destroy).pack(
            anchor=tk.E, pady=(12, 0)
        )
        notice.after(10_000, notice.destroy)


def main() -> None:
    root = tk.Tk()
    CollegeAssistantApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
