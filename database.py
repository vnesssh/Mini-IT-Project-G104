import sqlite3

conn = sqlite3.connect('reviews.db')

c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lecturer TEXT,
    rating INTEGER,
    comment TEXT
)
''')

conn.commit()
conn.close()

print("Database created successfully")