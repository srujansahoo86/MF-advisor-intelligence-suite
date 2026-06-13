import sqlite3
import json
import os
from contextlib import closing
from .config import Config
from .schemas import PendingAction

class Persistence:
    """Centralized persistence access layer over SQLite (and later vector DB)."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.SQLITE_DB_PATH
        self._init_db()
        
    def _init_db(self):
        """Initializes SQLite tables if they do not exist."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                # Key-Value store for themes, pulses, bookings
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS store (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                # Approval queue for MCP actions
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS pending_actions (
                        action_id TEXT PRIMARY KEY,
                        tool_name TEXT,
                        payload TEXT,
                        status TEXT
                    )
                ''')
            
    # --- General Key-Value Store (Pulse, Themes, Bookings) ---
    def set(self, key: str, value: dict):
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute('INSERT OR REPLACE INTO store (key, value) VALUES (?, ?)', 
                             (key, json.dumps(value)))
                         
    def get(self, key: str) -> dict:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute('SELECT value FROM store WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    # --- Approval Queue for Phase 4 MCP Orchestration ---
    def add_pending_action(self, action: PendingAction):
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute('''
                    INSERT INTO pending_actions (action_id, tool_name, payload, status)
                    VALUES (?, ?, ?, ?)
                ''', (action.action_id, action.tool_name, json.dumps(action.payload), action.status))
            
    def update_action_status(self, action_id: str, new_status: str):
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute('UPDATE pending_actions SET status = ? WHERE action_id = ?', 
                             (new_status, action_id))
                         
    def get_pending_actions(self) -> list[PendingAction]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute('SELECT action_id, tool_name, payload, status FROM pending_actions WHERE status = "PENDING"')
            actions = []
            for row in cursor.fetchall():
                actions.append(PendingAction(
                    action_id=row[0],
                    tool_name=row[1],
                    payload=json.loads(row[2]),
                    status=row[3]
                ))
            return actions
