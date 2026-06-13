import json
import random
import string
import sqlite3
from contextlib import closing
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import PendingAction
from .tools import doc_append, calendar_hold_creator, email_draft_generator

class MCPOrchestrator:
    """Manages the interception, queueing, and execution of MCP tools."""

    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)

    def _generate_action_id(self) -> str:
        """Generates a unique action identifier in format act-XXXX."""
        while True:
            suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
            action_id = f"act-{suffix}"
            
            # Check if this ID already exists in the database
            with closing(sqlite3.connect(self.persistence.db_path)) as conn:
                cursor = conn.execute("SELECT 1 FROM pending_actions WHERE action_id = ?", (action_id,))
                if cursor.fetchone() is None:
                    return action_id

    def list_pending(self) -> list[PendingAction]:
        """Returns all pending actions currently in the queue."""
        return self.persistence.get_pending_actions()

    def queue_action(self, tool_name: str, payload: dict) -> str:
        """
        Intercepts a tool invocation by creating a PendingAction in the queue.
        Does NOT execute the tool immediately.
        """
        valid_tools = ["Doc Append", "Calendar Hold Creator", "Email Draft Generator"]
        if tool_name not in valid_tools:
            raise ValueError(f"Unknown tool name: {tool_name}")

        action_id = self._generate_action_id()
        action = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            payload=payload,
            status="PENDING"
        )
        
        self.persistence.add_pending_action(action)
        return action_id

    def approve_action(self, action_id: str) -> dict:
        """
        Approves and executes a pending action, updating its status to APPROVED.
        Raises ValueError if action doesn't exist or is not pending.
        """
        # Fetch the action from SQLite
        with closing(sqlite3.connect(self.persistence.db_path)) as conn:
            cursor = conn.execute(
                "SELECT tool_name, payload, status FROM pending_actions WHERE action_id = ?", 
                (action_id,)
            )
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"Action {action_id} not found.")

        tool_name, payload_str, status = row
        if status != "PENDING":
            raise ValueError(f"Action {action_id} has already been resolved (current status: {status}).")

        payload = json.loads(payload_str)
        result = None

        # Execute corresponding tool
        if tool_name == "Doc Append":
            result = doc_append(
                file_path=payload.get("file_path"),
                content=payload.get("content")
            )
        elif tool_name == "Calendar Hold Creator":
            result = calendar_hold_creator(
                persistence=self.persistence,
                title=payload.get("title"),
                start_time=payload.get("start_time"),
                duration_minutes=payload.get("duration_minutes", 30),
                attendees=payload.get("attendees", [])
            )
        elif tool_name == "Email Draft Generator":
            result = email_draft_generator(
                persistence=self.persistence,
                recipient=payload.get("recipient"),
                subject=payload.get("subject"),
                topic=payload.get("topic")
            )
        else:
            raise ValueError(f"Unhandled tool name: {tool_name}")

        # Update action status to APPROVED
        self.persistence.update_action_status(action_id, "APPROVED")
        return result

    def reject_action(self, action_id: str) -> dict:
        """
        Rejects a pending action, updating its status to REJECTED.
        The tool is never executed.
        """
        with closing(sqlite3.connect(self.persistence.db_path)) as conn:
            cursor = conn.execute(
                "SELECT status FROM pending_actions WHERE action_id = ?", 
                (action_id,)
            )
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"Action {action_id} not found.")

        status = row[0]
        if status != "PENDING":
            raise ValueError(f"Action {action_id} has already been resolved (current status: {status}).")

        # Update action status to REJECTED
        self.persistence.update_action_status(action_id, "REJECTED")
        return {
            "status": "success",
            "message": f"Action {action_id} has been rejected."
        }
