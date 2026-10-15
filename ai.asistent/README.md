# College AI Assistant

A private, local study planner built with Python and Tkinter. It helps you track
coursework, prioritize what to study next, and get desktop reminders while the
app is open. It does not send your data to an AI service or require an API key.

## Run it

1. Install Python 3.10 or newer.
2. From this folder, run:

   ```powershell
   python college_ai_assistant.py
   ```

Tasks are stored in `~\.college_ai_assistant\planner.sqlite3` in your Windows
user profile. The app uses only Python's standard library.

## Use it

- Add a task with a due date in `YYYY-MM-DD HH:MM` format, priority, and
  estimated study time.
- Use **Suggest next task** for a local recommendation based on deadlines and
  priority.
- Mark finished tasks complete or delete tasks you no longer need.
- Tasks due now or earlier trigger a desktop reminder while the app is running.
  A reminder is shown once per task.
- The task list and summary show open, overdue, and next-seven-day task counts.

The prioritization is a simple local heuristic, not a hosted large language
model. No network connection or third-party packages are needed.

## Run tests

```powershell
python -m unittest
```
