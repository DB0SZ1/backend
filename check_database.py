import sqlite3

def list_memories():
    conn = sqlite3.connect('celebration.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, message, type, url FROM memories")
    rows = cursor.fetchall()
    print(f"Memory Entries: {len(rows)}")
    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Type: {row[3]}, URL: {row[4]}")
        print(f"  Content: {row[2][:100]}...")
    conn.close()

if __name__ == "__main__":
    list_memories()
