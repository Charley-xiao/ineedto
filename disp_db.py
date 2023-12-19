import sqlite3
from app import DATABASE

with sqlite3.connect(DATABASE) as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

print(tasks)
print(users)