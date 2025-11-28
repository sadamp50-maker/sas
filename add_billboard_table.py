import sqlite3

conn = sqlite3.connect("billboards.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS billboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    width REAL,
    height REAL,
    is_digital INTEGER DEFAULT 0
);
""")

conn.commit()
conn.close()

print("✅ 'billboards' table کامیابی سے شامل کر دیا گیا!")
