"""
Migration script for PostgreSQL - add is_flagged column and zone_comments table
"""

import os
import psycopg2
from urllib.parse import urlparse

# Get database URL from environment
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("[ERROR] DATABASE_URL environment variable not set")
    exit(1)

# Parse DATABASE_URL
url = urlparse(database_url)

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
conn.autocommit = True
cursor = conn.cursor()

print("Connected to PostgreSQL database")

# Add is_flagged column to zones table
try:
    cursor.execute("ALTER TABLE zones ADD COLUMN is_flagged BOOLEAN DEFAULT FALSE")
    print("[OK] Added is_flagged column to zones table")
except psycopg2.errors.DuplicateColumn:
    print("[OK] is_flagged column already exists")
except Exception as e:
    print(f"[ERROR] Error adding is_flagged column: {e}")

# Create zone_comments table
try:
    cursor.execute("""
        CREATE TABLE zone_comments (
            id SERIAL PRIMARY KEY,
            zone_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    print("[OK] Created zone_comments table")
except psycopg2.errors.DuplicateTable:
    print("[OK] zone_comments table already exists")
except Exception as e:
    print(f"[ERROR] Error creating zone_comments table: {e}")

cursor.close()
conn.close()

print("\n[OK] Migration completed successfully!")
