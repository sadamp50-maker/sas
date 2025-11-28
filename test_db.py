import sqlite3
import os

db_path = "billboards.db"

if not os.path.exists(db_path):
    print("❌ Database فائل نہیں ملی:", db_path)
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # تمام tables چیک کریں
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()

    if tables:
        print("✅ موجودہ Tables:")
        for t in tables:
            print(" -", t[0])
    else:
        print("⚠️ Database خالی ہے (ابھی کوئی table نہیں بنی)")

    conn.close()
