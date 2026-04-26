import sqlite3

def list_tables():
    conn = sqlite3.connect('celebration.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    for table in tables:
        tname = table[0]
        print(f"\n--- Table: {tname} ---")
        cursor.execute(f"PRAGMA table_info({tname})")
        columns = cursor.fetchall()
        print(f"Columns: {[c[1] for c in columns]}")
    conn.close()

if __name__ == "__main__":
    list_tables()
