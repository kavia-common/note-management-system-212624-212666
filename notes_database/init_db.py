#!/usr/bin/env python3
"""Initialize SQLite database for notes_database

This script initializes the local SQLite database with base tables and idempotently
ensures the notes table exists using a SQL migration. It:
- Enables PRAGMA foreign_keys=ON
- Creates base tables (existing behavior: app_info, users)
- Applies migrations/001_create_notes.sql if notes table is missing
- Writes connection helper files
- Prints a concise end status
"""

import sqlite3
import os
from contextlib import closing

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, but kept for consistency
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite, but kept for consistency
DB_PORT = "5000"  # Not used for SQLite, but kept for consistency

MIGRATIONS_DIR = "migrations"
NOTES_MIGRATION_FILE = os.path.join(MIGRATIONS_DIR, "001_create_notes.sql")

print("Starting SQLite setup...")

# Ensure migrations directory exists (non-fatal if already present)
os.makedirs(MIGRATIONS_DIR, exist_ok=True)

# Check if database already exists
db_exists = os.path.exists(DB_NAME)
if db_exists:
    print(f"SQLite database already exists at {DB_NAME}")
else:
    print("Creating new SQLite database...")

# Connect and enable foreign keys
with closing(sqlite3.connect(DB_NAME)) as conn:
    conn.isolation_level = None  # allow executing PRAGMA reliably
    with closing(conn.cursor()) as cursor:
        # Enable foreign keys (requirement 1)
        cursor.execute("PRAGMA foreign_keys = ON")

        # Begin transaction for schema operations
        cursor.execute("BEGIN")

        # Keep existing behavior: create initial schema tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Upsert initial data for app_info (existing behavior)
        cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
                       ("project_name", "notes_database"))
        cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
                       ("version", "0.1.0"))
        cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
                       ("author", "John Doe"))
        cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
                       ("description", ""))

        # Requirement 2: detect notes table and run migration if missing
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'")
        notes_exists = cursor.fetchone() is not None

        created_notes = False
        if not notes_exists:
            # Read and execute migration file
            try:
                with open(NOTES_MIGRATION_FILE, "r", encoding="utf-8") as f:
                    migration_sql = f.read()
                # executescript supports multiple statements
                conn.executescript(migration_sql)
                created_notes = True
            except FileNotFoundError:
                # Surface a clear error to help future debugging
                raise FileNotFoundError(
                    f"Required migration not found: {NOTES_MIGRATION_FILE}"
                )

        # Commit schema and seed updates
        cursor.execute("COMMIT")

        # Gather stats for concise status output
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_count = cursor.fetchone()[0] or 0

        # app_info count (best effort)
        try:
            cursor.execute("SELECT COUNT(*) FROM app_info")
            record_count = cursor.fetchone()[0] or 0
        except sqlite3.Error:
            record_count = 0

# Save connection information to a file
current_dir = os.getcwd()
connection_string = f"sqlite:///{current_dir}/{DB_NAME}"

try:
    with open("db_connection.txt", "w") as f:
        f.write(f"# SQLite connection methods:\n")
        f.write(f"# Python: sqlite3.connect('{DB_NAME}')\n")
        f.write(f"# Connection string: {connection_string}\n")
        f.write(f"# File path: {current_dir}/{DB_NAME}\n")
    print("Connection information saved to db_connection.txt")
except Exception as e:
    print(f"Warning: Could not save connection info: {e}")

# Create environment variables file for Node.js viewer
db_path = os.path.abspath(DB_NAME)

# Ensure db_visualizer directory exists
if not os.path.exists("db_visualizer"):
    os.makedirs("db_visualizer", exist_ok=True)
    print("Created db_visualizer directory")

try:
    with open("db_visualizer/sqlite.env", "w") as f:
        f.write(f"export SQLITE_DB=\"{db_path}\"\n")
    print("Environment variables saved to db_visualizer/sqlite.env")
except Exception as e:
    print(f"Warning: Could not save environment variables: {e}")

# Concise final status message (requirement 4)
status_parts = []
status_parts.append("SQLite setup complete")
status_parts.append(f"DB={DB_NAME}")
status_parts.append(f"tables={table_count}")
status_parts.append(f"app_info_records={record_count}")
status_parts.append("notes_table=" + ("created" if not db_exists and created_notes or (created_notes) else "ready"))

print(" | ".join(status_parts))
print(f"Location: {current_dir}/{DB_NAME}")
print(f"Connect: sqlite3 {DB_NAME}")
