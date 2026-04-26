import sqlite3

def list_tables(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\n--- Database: {db_name} ---")
    print(f"Tables: {[t[0] for t in tables]}")
    for table in tables:
        tname = table[0]
        print(f"\n--- Table: {tname} ---")
        cursor.execute(f"PRAGMA table_info({tname})")
        columns = cursor.fetchall()
        print(f"Columns: {[c[1] for c in columns]}")
        
        # Check first few rows
        cursor.execute(f"SELECT * FROM {tname} LIMIT 5")
        rows = cursor.fetchall()
        print(f"Rows: {len(rows)}")
    conn.close()

if __name__ == "__main__":
    list_tables('celebration_old.db')
