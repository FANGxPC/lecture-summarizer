import sqlite3
import json
import uuid
import os
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "audio_app.db")


def get_connection(*, with_row_factory: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    if with_row_factory:
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL,
                transcript TEXT,
                summary TEXT,
                topics TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)")

def create_task(filename: str) -> str:
    task_id = str(uuid.uuid4())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (id, filename, status) VALUES (?, ?, ?)",
            (task_id, filename, "processing")
        )
    return task_id

def update_task_status(task_id: str, status: str, transcript: Optional[str] = None, 
                       summary: Optional[str] = None, topics: Optional[list] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        values = [status]
        
        if transcript is not None:
            updates.append("transcript = ?")
            values.append(transcript)
        if summary is not None:
            updates.append("summary = ?")
            values.append(summary)
        if topics is not None:
            updates.append("topics = ?")
            values.append(json.dumps(topics))
            
        values.append(task_id)
        
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(values))

def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with get_connection(with_row_factory=True) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
    
    if row:
        result = dict(row)
        if result.get("topics"):
            result["topics"] = json.loads(result["topics"])
        return result
    return None

def get_all_tasks() -> list[Dict[str, Any]]:
    with get_connection(with_row_factory=True) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
    
    results = []
    for row in rows:
        result = dict(row)
        if result.get("topics"):
            result["topics"] = json.loads(result["topics"])
        results.append(result)
    return results

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
