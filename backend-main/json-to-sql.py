import json
import sys

def json_to_sql():
    print("Converting JSON backups to SQL...")
    
    sql_lines = []
    sql_lines.append("-- Railway Database Backup")
    sql_lines.append("-- Generated from JSON exports")
    sql_lines.append("")
    sql_lines.append("BEGIN TRANSACTION;")
    sql_lines.append("")
    
    # Messages
    try:
        with open("backup_messages.json", "r") as f:
            data = json.load(f)
            messages = data.get('messages', [])
            for msg in messages:
                name = msg.get('name', '').replace("'", "''")
                relationship = msg.get('relationship', '').replace("'", "''")
                message = msg.get('message', '').replace("'", "''")
                created_at = msg.get('created_at', '')
                
                sql_lines.append(
                    f"INSERT INTO messages (name, relationship, message, created_at) "
                    f"VALUES ('{name}', '{relationship}', '{message}', '{created_at}');"
                )
            print(f"✓ Converted {len(messages)} messages")
    except Exception as e:
        print(f"⚠ Error with messages: {e}")
    
    sql_lines.append("")
    
    # Memories
    try:
        with open("backup_memories.json", "r") as f:
            data = json.load(f)
            memories = data.get('memories', [])
            for mem in memories:
                name = mem.get('name', '').replace("'", "''")
                caption = mem.get('caption', '').replace("'", "''")
                image_url = mem.get('image_url', '').replace("'", "''")
                cloudinary_id = mem.get('cloudinary_id', '').replace("'", "''")
                mem_type = mem.get('type', 'photo')
                storage_type = mem.get('storage_type', 'cloudinary')
                file_size = mem.get('file_size', 0) or 0
                created_at = mem.get('created_at', '')
                
                sql_lines.append(
                    f"INSERT INTO memories (name, caption, image_url, cloudinary_id, type, storage_type, file_size, created_at) "
                    f"VALUES ('{name}', '{caption}', '{image_url}', '{cloudinary_id}', '{mem_type}', '{storage_type}', {file_size}, '{created_at}');"
                )
            print(f"✓ Converted {len(memories)} memories")
    except Exception as e:
        print(f"⚠ Error with memories: {e}")
    
    sql_lines.append("")
    sql_lines.append("COMMIT;")
    
    # Write to file
    with open("backup_from_railway.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))
    
    print(f"\n✅ SQL backup created: backup_from_railway.sql")
    print(f"Total lines: {len(sql_lines)}")

if __name__ == "__main__":
    json_to_sql()