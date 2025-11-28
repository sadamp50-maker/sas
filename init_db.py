import sqlite3

# اگر فائل موجود نہ ہو تو یہ خود نئی billboards.db فائل بنا دے گا
conn = sqlite3.connect("billboards.db")
cur = conn.cursor()

# Billboard کی جدول (table) بنائیں
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
print("✅ Database اور Table کامیابی سے بن گئے — billboards.db تیار ہے!")
