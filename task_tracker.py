import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import threading
from plyer import notification

# Database setup
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        deadline TEXT NOT NULL,
        problems TEXT,
        requirements TEXT
    )''')
    conn.commit()
    conn.close()

# Add a new task
def add_task(title, deadline, problems, requirements):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (title, deadline, problems, requirements) VALUES (?, ?, ?, ?)',
              (title, deadline, problems, requirements))
    conn.commit()
    conn.close()

# Get all tasks
def get_tasks():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tasks')
    tasks = c.fetchall()
    conn.close()
    return tasks

# Delete a task
def delete_task(task_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id=?', (task_id,))
    conn.commit()
    conn.close()

# Reminder function
def send_reminders():
    tasks = get_tasks()
    now = datetime.now()
    for task in tasks:
        task_id, title, deadline, problems, requirements = task
        deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
        if deadline_dt - now <= timedelta(days=1) and deadline_dt > now:
            # Desktop notification
            notification.notify(
                title=f"Task Reminder: {title}",
                message=f"Due: {deadline}\nProblems: {problems}\nRequirements: {requirements}",
                timeout=10
            )
            print(f"Reminder: Task '{title}' is due on {deadline}!")

# Scheduler setup (runs in background)
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminders, 'interval', hours=12)
    scheduler.start()

# Ensure scheduler runs only once
if 'scheduler_started' not in st.session_state:
    threading.Thread(target=start_scheduler, daemon=True).start()
    st.session_state['scheduler_started'] = True

# Initialize DB
init_db()

st.title('Task Tracker')

# Add Task Form
with st.form('Add Task'):
    title = st.text_input('Task Title')
    deadline = st.date_input('Deadline')
    problems = st.text_area('Problems Facing')
    requirements = st.text_area('Requirements to Complete Efficiently')
    submitted = st.form_submit_button('Add Task')
    if submitted:
        add_task(title, deadline.strftime('%Y-%m-%d'), problems, requirements)
        st.success('Task added!')

# Show Tasks
tasks = get_tasks()
st.subheader('All Tasks')
for task in tasks:
    task_id, title, deadline, problems, requirements = task
    st.markdown(f"**{title}** (Due: {deadline})")
    st.markdown(f"- **Problems:** {problems}")
    st.markdown(f"- **Requirements:** {requirements}")
    if st.button(f'Delete Task {task_id}', key=f'del{task_id}'):
        delete_task(task_id)
        st.experimental_rerun()
    st.markdown('---')

st.info('Reminders will be printed to the console a day before the deadline. For email/desktop notifications, let me know!') 