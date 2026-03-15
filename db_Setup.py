"""
Database Migration Script
Adds missing columns to existing celebration.db
Run this ONCE to update your database schema
"""

import sqlite3

def migrate_database(db_path='celebration.db'):
    """Add missing columns to memories table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 Starting database migration...")
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(memories)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    print(f"📋 Existing columns: {existing_columns}")
    
    # Add missing columns if they don't exist
    columns_to_add = [
        ("storage_type", "TEXT DEFAULT 'cloudinary'"),
        ("file_size", "INTEGER")
    ]
    
    for column_name, column_def in columns_to_add:
        if column_name not in existing_columns:
            try:
                alter_query = f"ALTER TABLE memories ADD COLUMN {column_name} {column_def}"
                cursor.execute(alter_query)
                print(f"✅ Added column: {column_name}")
            except sqlite3.Error as e:
                print(f"⚠️ Error adding {column_name}: {e}")
        else:
            print(f"ℹ️ Column {column_name} already exists")
    
    # Verify final schema
    cursor.execute("PRAGMA table_info(memories)")
    final_columns = cursor.fetchall()
    print("\n📊 Final table schema:")
    for col in final_columns:
        print(f"  - {col[1]} ({col[2]})")
    
    conn.commit()
    conn.close()
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate_database()