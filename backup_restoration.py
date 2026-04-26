"""
Database Backup Restoration Module for SQLite
Automatically restores data from backup.sql on startup
"""

import sqlite3
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupRestoration:
    """
    Handles automatic restoration of database backups on startup.
    Checks if backup exists and data is missing, then restores it.
    """

    def __init__(self, db_path: str = 'celebration.db', backup_path: str = 'backup.sql'):
        """
        Initialize backup restoration system.

        Args:
            db_path: Path to the SQLite database file
            backup_path: Path to the backup SQL file
        """
        self.db_path = db_path
        self.backup_path = backup_path
        self.restored_count = 0
        self.backup_exists = os.path.exists(backup_path)

    def should_restore(self, conn: sqlite3.Connection) -> bool:
        """
        Determine if backup should be restored.
        Restores if:
        1. Backup file exists
        2. Database tables are empty

        Args:
            conn: SQLite connection

        Returns:
            bool: True if backup should be restored
        """
        if not self.backup_exists:
            logger.info("📦 No backup.sql file found - skipping restoration")
            return False

        try:
            cursor = conn.cursor()

            # Check if messages table has data
            cursor.execute("SELECT COUNT(*) FROM messages")
            messages_count = cursor.fetchone()[0]

            # Check if memories table has data
            cursor.execute("SELECT COUNT(*) FROM memories")
            memories_count = cursor.fetchone()[0]

            cursor.close()

            if messages_count > 0 or memories_count > 0:
                logger.info(
                    f"✅ Database already has data "
                    f"(messages: {messages_count}, memories: {memories_count}) - skipping restore"
                )
                return False

            logger.info("📋 Database is empty and backup.sql exists - will restore data")
            return True

        except Exception as e:
            logger.error(f"❌ Error checking if restore needed: {str(e)}")
            return False

    def restore(self, conn: sqlite3.Connection) -> bool:
        """
        Restore data from backup.sql file.

        Args:
            conn: SQLite connection

        Returns:
            bool: True if restoration was successful
        """
        if not self.backup_exists:
            logger.warning("📦 Backup file not found at", self.backup_path)
            return False

        try:
            logger.info(f"🔄 Starting backup restoration from {self.backup_path}...")
            start_time = datetime.now()

            # Read the backup SQL file
            with open(self.backup_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # Execute the SQL script
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()
            cursor.close()

            # Count restored records
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            messages_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM memories")
            memories_count = cursor.fetchone()[0]
            cursor.close()

            elapsed_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"✅ Backup restoration completed successfully! "
                f"({elapsed_time:.2f}s) - "
                f"Restored {messages_count} messages + {memories_count} memories"
            )

            self.restored_count = messages_count + memories_count
            return True

        except FileNotFoundError:
            logger.error(f"❌ Backup file not found: {self.backup_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Error during backup restoration: {str(e)}")
            logger.error(f"   Error type: {type(e).__name__}")
            return False

    def get_status(self) -> dict:
        """
        Get the status of backup restoration.

        Returns:
            dict: Status information
        """
        return {
            'backup_file_exists': self.backup_exists,
            'backup_path': self.backup_path,
            'records_restored': self.restored_count,
            'database_path': self.db_path,
        }

    def create_backup(self, conn: sqlite3.Connection, output_path: str = None) -> bool:
        """
        Create a new backup of current database state.

        Args:
            conn: SQLite connection
            output_path: Where to save backup (default: backup_TIMESTAMP.sql)

        Returns:
            bool: True if backup was created successfully
        """
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'backup_{timestamp}.sql'

        try:
            logger.info(f"💾 Creating backup to {output_path}...")

            cursor = conn.cursor()

            with open(output_path, 'w', encoding='utf-8') as f:
                # Write header
                f.write('-- Database Backup\n')
                f.write(f'-- Generated: {datetime.now().isoformat()}\n\n')
                f.write('BEGIN TRANSACTION;\n\n')

                # Backup messages table
                cursor.execute('SELECT * FROM messages ORDER BY created_at DESC')
                messages = cursor.fetchall()
                cursor.execute('PRAGMA table_info(messages)')
                columns = [col[1] for col in cursor.fetchall()]

                for msg in messages:
                    values = ', '.join([
                        f"'{str(val).replace(chr(39), chr(39) * 2)}'" if val is not None else 'NULL'
                        for val in msg
                    ])
                    f.write(f"INSERT INTO messages ({', '.join(columns)}) VALUES ({values});\n")

                f.write('\n')

                # Backup memories table
                cursor.execute('SELECT * FROM memories ORDER BY created_at DESC')
                memories = cursor.fetchall()
                cursor.execute('PRAGMA table_info(memories)')
                columns = [col[1] for col in cursor.fetchall()]

                for mem in memories:
                    values = ', '.join([
                        f"'{str(val).replace(chr(39), chr(39) * 2)}'" if val is not None else 'NULL'
                        for val in mem
                    ])
                    f.write(f"INSERT INTO memories ({', '.join(columns)}) VALUES ({values});\n")

                f.write('\nCOMMIT;\n')

            cursor.close()
            logger.info(f"✅ Backup created successfully at {output_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating backup: {str(e)}")
            return False


def auto_restore_backup_on_init(db_path: str = 'celebration.db', backup_path: str = 'backup.sql'):
    """
    Automatically restore backup if database is empty.
    Call this during app initialization.

    Args:
        db_path: Path to the SQLite database
        backup_path: Path to the backup SQL file

    Returns:
        BackupRestoration: Restoration object with status
    """
    restoration = BackupRestoration(db_path, backup_path)

    try:
        conn = sqlite3.connect(db_path)

        if restoration.should_restore(conn):
            success = restoration.restore(conn)
            if success:
                logger.info("🎉 Backup data successfully integrated into database")
            else:
                logger.warning("⚠️  Backup restoration failed, continuing with empty database")
        else:
            logger.info("⏭️  Backup restoration skipped - database already has data or no backup file")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Error during auto-restore initialization: {str(e)}")

    return restoration
