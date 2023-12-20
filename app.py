from flask import Flask, render_template, request, redirect, url_for, make_response
import sqlite3
from datetime import datetime, timedelta
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import tomli
import argparse

app = Flask(__name__)

DATABASE = 'tasks.db'

with open('config.toml','rb') as f:
    config = tomli.load(f)
    SERVER = config['smtp']['server']
    PORT = config['smtp']['port']
    USERNAME = config['smtp']['username']
    PASSWORD = config['smtp']['password']
    HOURS = config['notification']['hours']

def make_parser():
    parser = argparse.ArgumentParser(
        description='A simple task manager web application.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to.')
    parser.add_argument('--port', default=5000, type=int, help='Port to bind to.')
    return parser

args = None


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


init_db()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


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


@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('user_id', '', expires=0)
    return response


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

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')


def check_due_tasks():
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE due_date <= ?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        due_tasks = cursor.fetchall()

    for task in due_tasks:
        send_email_notification(task[1], task[2], task[3])


def check_countdown_tasks():
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE due_date <= ? AND due_date >= ?",
                       ((datetime.now() + timedelta(hours=HOURS)).strftime('%Y-%m-%d %H:%M:%S'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        countdown_tasks = cursor.fetchall()

    for task in countdown_tasks:
        send_email_notification(task[1], task[2], task[3])


def send_email_notification(description, due_date, user_id):
    if not user_id:
        return

    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    if user and user[1]:
        to_email = user[1]
        subject = "Task Due Reminder"
        body = f"Task '{description}' is due on {due_date.split('T')[0]} {due_date.split('T')[1]}!"

        message = MIMEMultipart('alternative')
        message['From'] = USERNAME
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL(SERVER, PORT) as server:
            server.login(USERNAME, PASSWORD)
            print(f'Sending email to {to_email}...')
            server.sendmail(USERNAME, to_email, message.as_string())


if __name__ == '__main__':
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(check_due_tasks, 'interval', hours=HOURS)
    scheduler.add_job(check_countdown_tasks, 'interval', hours=HOURS)
    scheduler.start()

    parser = make_parser()
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=True)
