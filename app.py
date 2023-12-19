from flask import Flask, render_template, request, redirect, url_for, make_response
import sqlite3
from datetime import datetime, timedelta
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

DATABASE = 'tasks.db'

TURBOSMTP_SERVER = 'your_turbosmtp_server'
TURBOSMTP_PORT = 587
TURBOSMTP_USERNAME = 'your_turbosmtp_username'
TURBOSMTP_PASSWORD = 'your_turbosmtp_password'

# Create a table to store users if it doesn't exist
def init_db():
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                due_date TEXT,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        connection.commit()

# Initialize the database
init_db()

# Function to hash the password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed_password = hash_password(password)

        with sqlite3.connect(DATABASE) as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)",
                           (email, hashed_password))
            connection.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed_password = hash_password(password)

        with sqlite3.connect(DATABASE) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?",
                           (email, hashed_password))
            user = cursor.fetchone()

        if user:
            response = make_response(redirect(url_for('index')))
            response.set_cookie('user_id', str(user[0]), httponly=True)
            return response
        else:
            return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

# Route to display tasks for the authenticated user
@app.route('/')
def index():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY due_date", (user_id,))
        tasks = cursor.fetchall()

    return render_template('index.html', tasks=tasks)

# Route to add a new task
@app.route('/add', methods=['POST'])
def add_task():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    description = request.form['description']
    due_date = request.form['due_date']

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO tasks (description, due_date, user_id) VALUES (?, ?, ?)",
                       (description, due_date, user_id))
        connection.commit()

    return redirect(url_for('index'))

# Route to edit a task
@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    if request.method == 'POST':
        description = request.form['description']
        due_date = request.form['due_date']

        with sqlite3.connect(DATABASE) as connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE tasks SET description = ?, due_date = ? WHERE id = ? AND user_id = ?",
                           (description, due_date, task_id, user_id))
            connection.commit()

        return redirect(url_for('index'))

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        task = cursor.fetchone()

    return render_template('edit.html', task=task)

# Route to logout the user
@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('user_id', '', expires=0)
    return response

# Route to delete a task
@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        connection.commit()

    return redirect(url_for('index'))

# Check for due tasks and send notifications
def check_due_tasks():
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE due_date <= ?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        due_tasks = cursor.fetchall()

    for task in due_tasks:
        send_email_notification(task[1], task[2])

# Function to send email notification using TurboSMTP
def send_email_notification(description, due_date):
    user_id = request.cookies.get('user_id')
    if not user_id:
        return

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    if user and user[1]:  # Check if the user has an email address
        to_email = user[1]
        subject = "Task Due Reminder"
        body = f"Task '{description}' is due on {due_date}!"

        # Set up the MIME
        message = MIMEMultipart()
        message['From'] = 'your_email@example.com'  # Replace with your sender email
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        # Connect to the TurboSMTP server
        with smtplib.SMTP(TURBOSMTP_SERVER, TURBOSMTP_PORT) as server:
            server.starttls()
            server.login(TURBOSMTP_USERNAME, TURBOSMTP_PASSWORD)
            server.sendmail('your_email@example.com', to_email, message.as_string())

# Run the check_due_tasks function every day
if __name__ == '__main__':
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(check_due_tasks, 'interval', days=1)
    scheduler.start()

    app.run(debug=True)
