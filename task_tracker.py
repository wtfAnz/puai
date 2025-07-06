import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import time
import os

# Database setup with migration support
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        deadline TEXT NOT NULL,
        problems TEXT,
        requirements TEXT,
        priority TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Check if new columns exist and add them if they don't
    c.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'priority' not in columns:
        c.execute('ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT "Medium"')
        print("Added priority column")
    
    if 'status' not in columns:
        c.execute('ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT "Pending"')
        print("Added status column")
    
    if 'created_at' not in columns:
        c.execute('ALTER TABLE tasks ADD COLUMN created_at TEXT')
        # Update existing rows with current timestamp
        c.execute('UPDATE tasks SET created_at = datetime("now") WHERE created_at IS NULL')
        print("Added created_at column")
    
    conn.commit()
    conn.close()

# Add a new task
def add_task(title, deadline, problems, requirements, priority='Medium'):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # Check if new columns exist
    c.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'priority' in columns and 'status' in columns and 'created_at' in columns:
        # New schema with all columns
        c.execute('''INSERT INTO tasks (title, deadline, problems, requirements, priority, status, created_at) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (title, deadline, problems, requirements, priority, 'Pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    else:
        # Old schema - just basic columns
        c.execute('INSERT INTO tasks (title, deadline, problems, requirements) VALUES (?, ?, ?, ?)',
                  (title, deadline, problems, requirements))
    
    conn.commit()
    conn.close()

# Get all tasks with optional filtering and safe column handling
def get_tasks(status_filter=None, sort_by='deadline'):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # Get column information to handle different database schemas
    c.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in c.fetchall()]
    
    # Build query based on available columns
    query = 'SELECT id, title, deadline, problems, requirements'
    
    # Add optional columns if they exist
    if 'priority' in columns:
        query += ', priority'
    else:
        query += ', "Medium" as priority'
    
    if 'status' in columns:
        query += ', status'
    else:
        query += ', "Pending" as status'
    
    if 'created_at' in columns:
        query += ', created_at'
    else:
        query += ', datetime("now") as created_at'
    
    query += ' FROM tasks'
    
    params = []
    
    if status_filter and 'status' in columns:
        query += ' WHERE status = ?'
        params.append(status_filter)
    
    if sort_by == 'deadline':
        query += ' ORDER BY deadline ASC'
    elif sort_by == 'priority' and 'priority' in columns:
        query += ' ORDER BY CASE priority WHEN "High" THEN 1 WHEN "Medium" THEN 2 WHEN "Low" THEN 3 END'
    elif sort_by == 'created' and 'created_at' in columns:
        query += ' ORDER BY created_at DESC'
    
    c.execute(query, params)
    tasks = c.fetchall()
    conn.close()
    return tasks

# Update task status
def update_task_status(task_id, status):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
    conn.commit()
    conn.close()

# Delete a task
def delete_task(task_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id=?', (task_id,))
    conn.commit()
    conn.close()

# Get tasks due soon with safe column handling
def get_due_soon_tasks():
    tasks = get_tasks()
    now = datetime.now()
    due_soon = []
    
    for task in tasks:
        # Handle different tuple lengths safely
        if len(task) < 7:
            continue
            
        task_id, title, deadline, problems, requirements, priority, status = task[:7]
        created_at = task[7] if len(task) > 7 else None
        
        if status == 'Completed':
            continue
            
        try:
            deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
            days_until = (deadline_dt - now).days
            
            if days_until <= 1 and days_until >= 0:
                due_soon.append((task, days_until))
        except ValueError:
            continue
    
    return due_soon

# Enhanced reminder function
def send_reminders():
    due_soon = get_due_soon_tasks()
    
    for task_info, days_until in due_soon:
        # Handle different tuple lengths safely
        task_id, title, deadline, problems, requirements = task_info[:5]
        priority = task_info[5] if len(task_info) > 5 else 'Medium'
        status = task_info[6] if len(task_info) > 6 else 'Pending'
        created_at = task_info[7] if len(task_info) > 7 else None
        
        urgency = "TODAY" if days_until == 0 else "TOMORROW"
        
        # Try desktop notification (will work if plyer is installed)
        try:
            from plyer import notification
            notification.notify(
                title=f"⚠️ Task Due {urgency}",
                message=f"{title}\nDue: {deadline}\nPriority: {priority}",
                timeout=15
            )
        except ImportError:
            pass
        
        # Console notification (always works)
        print(f"🔔 REMINDER: Task '{title}' is due {urgency} ({deadline})!")
        print(f"   Priority: {priority}")
        if problems:
            print(f"   Problems: {problems}")
        print("-" * 50)

# Scheduler setup with error handling
def start_scheduler():
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(send_reminders, 'interval', hours=6)  # Check every 6 hours
        scheduler.start()
        print("✅ Reminder scheduler started successfully")
    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")

# Ensure scheduler runs only once per session
if 'scheduler_started' not in st.session_state:
    try:
        threading.Thread(target=start_scheduler, daemon=True).start()
        st.session_state['scheduler_started'] = True
    except Exception as e:
        st.error(f"Failed to start background scheduler: {e}")

# Initialize DB
init_db()

# Streamlit App
st.set_page_config(page_title="Task Tracker", page_icon="📋", layout="wide")

st.title('📋 Task Tracker')
st.markdown("*Stay organized and never miss a deadline!*")

# Sidebar for filters and stats
st.sidebar.header("📊 Dashboard")

# Task statistics with safe indexing
all_tasks = get_tasks()
pending_tasks = len([t for t in all_tasks if len(t) > 6 and t[6] == 'Pending'])
completed_tasks = len([t for t in all_tasks if len(t) > 6 and t[6] == 'Completed'])
due_soon = len(get_due_soon_tasks())

col1, col2, col3 = st.sidebar.columns(3)
with col1:
    st.metric("Pending", pending_tasks)
with col2:
    st.metric("Completed", completed_tasks)
with col3:
    st.metric("Due Soon", due_soon, delta=f"-{due_soon}" if due_soon > 0 else None)

# Filters
st.sidebar.header("🔍 Filters")
status_filter = st.sidebar.selectbox(
    "Filter by Status",
    ["All", "Pending", "Completed", "In Progress"]
)
sort_by = st.sidebar.selectbox(
    "Sort by",
    ["deadline", "priority", "created"]
)

# Main content area
col1, col2 = st.columns([1, 2])

with col1:
    st.header("➕ Add New Task")
    
    # Add Task Form
    with st.form('add_task_form'):
        title = st.text_input('Task Title *', help="Enter a clear, descriptive title")
        deadline = st.date_input('Deadline *', min_value=datetime.now().date())
        priority = st.selectbox('Priority', ['Low', 'Medium', 'High'], index=1)
        problems = st.text_area('Problems/Challenges', help="What obstacles do you foresee?")
        requirements = st.text_area('Requirements', help="What do you need to complete this task?")
        
        submitted = st.form_submit_button('Add Task', type="primary")
        
        if submitted:
            if title.strip():
                add_task(title.strip(), deadline.strftime('%Y-%m-%d'), problems.strip(), requirements.strip(), priority)
                st.success('✅ Task added successfully!')
                st.rerun()
            else:
                st.error('Please enter a task title')

with col2:
    st.header("📝 Your Tasks")
    
    # Get filtered tasks
    filter_param = None if status_filter == "All" else status_filter
    tasks = get_tasks(status_filter=filter_param, sort_by=sort_by)
    
    if not tasks:
        st.info("No tasks found. Add your first task to get started!")
    else:
        for task in tasks:
            # Handle different tuple lengths safely
            task_id, title, deadline, problems, requirements = task[:5]
            priority = task[5] if len(task) > 5 else 'Medium'
            status = task[6] if len(task) > 6 else 'Pending'
            created_at = task[7] if len(task) > 7 else None
            
            # Determine if task is overdue
            try:
                deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
                days_until = (deadline_dt - datetime.now()).days
                is_overdue = days_until < 0 and status != 'Completed'
                is_due_soon = 0 <= days_until <= 1 and status != 'Completed'
            except ValueError:
                is_overdue = False
                is_due_soon = False
            
            # Task container with color coding
            if is_overdue:
                container_type = "error"
                status_emoji = "🚨"
            elif is_due_soon:
                container_type = "warning"
                status_emoji = "⚠️"
            elif status == 'Completed':
                container_type = "success"
                status_emoji = "✅"
            else:
                container_type = "info"
                status_emoji = "📋"
            
            with st.container():
                st.markdown(f"### {status_emoji} {title}")
                
                # Task details in columns
                detail_col1, detail_col2, detail_col3 = st.columns([2, 1, 1])
                
                with detail_col1:
                    st.markdown(f"**Due:** {deadline}")
                    if problems:
                        st.markdown(f"**Problems:** {problems}")
                    if requirements:
                        st.markdown(f"**Requirements:** {requirements}")
                
                with detail_col2:
                    st.markdown(f"**Priority:** {priority}")
                    st.markdown(f"**Status:** {status}")
                
                with detail_col3:
                    # Status update buttons
                    if status != 'Completed':
                        if st.button('Mark Complete', key=f'complete_{task_id}', type="primary"):
                            update_task_status(task_id, 'Completed')
                            st.rerun()
                        
                        if status != 'In Progress':
                            if st.button('Start Working', key=f'progress_{task_id}'):
                                update_task_status(task_id, 'In Progress')
                                st.rerun()
                    else:
                        if st.button('Mark Pending', key=f'pending_{task_id}'):
                            update_task_status(task_id, 'Pending')
                            st.rerun()
                    
                    # Delete button
                    if st.button('🗑️ Delete', key=f'delete_{task_id}', help="Delete this task"):
                        delete_task(task_id)
                        st.rerun()
                
                st.markdown("---")

# Footer with tips
st.markdown("---")
st.markdown("### 💡 Tips")
st.markdown("""
- **Reminders**: The app checks for due tasks every 6 hours and sends notifications
- **Desktop Notifications**: Install `plyer` package for desktop notifications: `pip install plyer`
- **Priority Levels**: Use High for urgent tasks, Medium for important ones, Low for nice-to-have
- **Status Tracking**: Move tasks through Pending → In Progress → Completed
""")

# Show upcoming deadlines
if due_soon > 0:
    st.warning(f"⚠️ You have {due_soon} task(s) due soon!")
    due_tasks = get_due_soon_tasks()
    for task_info, days_until in due_tasks:
        # Handle different tuple lengths safely
        task_id, title, deadline, problems, requirements = task_info[:5]
        priority = task_info[5] if len(task_info) > 5 else 'Medium'
        status = task_info[6] if len(task_info) > 6 else 'Pending'
        urgency = "today" if days_until == 0 else "tomorrow"
        st.markdown(f"- **{title}** is due {urgency} ({deadline}) - Priority: {priority}")