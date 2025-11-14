"""
Migration script to add is_flagged column and zone_comments table
"""

import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'data', 'bist_scanner.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Add is_flagged column to zones table
    cursor.execute("ALTER TABLE zones ADD COLUMN is_flagged BOOLEAN DEFAULT 0")
    print("[OK] Added is_flagged column to zones table")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("[OK] is_flagged column already exists")
    else:
        print(f"[ERROR] Error adding is_flagged column: {e}")

try:
    # Create zone_comments table
    cursor.execute("""
        CREATE TABLE zone_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES zones(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    print("[OK] Created zone_comments table")
except sqlite3.OperationalError as e:
    if "already exists" in str(e).lower():
        print("[OK] zone_comments table already exists")
    else:
        print(f"[ERROR] Error creating zone_comments table: {e}")

conn.commit()
conn.close()

print("\n[OK] Migration completed successfully!")
