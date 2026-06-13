import os
import pytest
import sqlite3
from contextlib import closing
from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.config import Config

TEST_DB_PATH = "./data/test_phase4.db"
TEST_APPEND_FILE = "./data/test_append.txt"

@pytest.fixture
def clean_env():
    # Setup
    for path in [TEST_DB_PATH, TEST_APPEND_FILE]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    yield
    # Teardown
    for path in [TEST_DB_PATH, TEST_APPEND_FILE]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

has_groq_key = bool(os.getenv("GROQ_API_KEY"))
skip_no_groq = pytest.mark.skipif(not has_groq_key, reason="GROQ_API_KEY environment variable not set")

# 1. Interception test
def test_tool_queue_interception(clean_env):
    orchestrator = MCPOrchestrator(db_path=TEST_DB_PATH)
    
    # Queue a Doc Append action
    payload = {
        "file_path": TEST_APPEND_FILE,
        "content": "Line 1: intercepted content"
    }
    action_id = orchestrator.queue_action("Doc Append", payload)
    
    assert action_id is not None
    assert action_id.startswith("act-")
    
    # Assert it is PENDING in SQLite
    pending_list = orchestrator.list_pending()
    assert len(pending_list) == 1
    assert pending_list[0].action_id == action_id
    assert pending_list[0].tool_name == "Doc Append"
    assert pending_list[0].status == "PENDING"
    assert pending_list[0].payload["content"] == "Line 1: intercepted content"
    
    # Verify the side effect HAS NOT happened yet
    assert not os.path.exists(TEST_APPEND_FILE)

# 2. Approve execution test
def test_approve_executes_exactly_once(clean_env):
    orchestrator = MCPOrchestrator(db_path=TEST_DB_PATH)
    
    payload = {
        "file_path": TEST_APPEND_FILE,
        "content": "Line 1: approved content"
    }
    action_id = orchestrator.queue_action("Doc Append", payload)
    
    # Approve and execute
    result = orchestrator.approve_action(action_id)
    assert result["status"] == "success"
    
    # Verify the side effect HAS occurred
    assert os.path.exists(TEST_APPEND_FILE)
    with open(TEST_APPEND_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert lines == ["Line 1: approved content"]
    
    # Verify status in DB is updated to APPROVED (not in list_pending)
    assert len(orchestrator.list_pending()) == 0
    
    with closing(sqlite3.connect(TEST_DB_PATH)) as conn:
        cursor = conn.execute("SELECT status FROM pending_actions WHERE action_id = ?", (action_id,))
        status = cursor.fetchone()[0]
    assert status == "APPROVED"
    
    # Verify trying to approve it again raises ValueError
    with pytest.raises(ValueError, match="already been resolved"):
        orchestrator.approve_action(action_id)

# 3. Reject never executes test
def test_reject_never_executes(clean_env):
    orchestrator = MCPOrchestrator(db_path=TEST_DB_PATH)
    
    payload = {
        "file_path": TEST_APPEND_FILE,
        "content": "Line 1: rejected content"
    }
    action_id = orchestrator.queue_action("Doc Append", payload)
    
    # Reject action
    result = orchestrator.reject_action(action_id)
    assert result["status"] == "success"
    
    # Verify the side effect HAS NOT occurred
    assert not os.path.exists(TEST_APPEND_FILE)
    
    # Verify status in DB is updated to REJECTED (not in list_pending)
    assert len(orchestrator.list_pending()) == 0
    
    with closing(sqlite3.connect(TEST_DB_PATH)) as conn:
        cursor = conn.execute("SELECT status FROM pending_actions WHERE action_id = ?", (action_id,))
        status = cursor.fetchone()[0]
    assert status == "REJECTED"
    
    # Verify trying to approve a rejected action raises ValueError
    with pytest.raises(ValueError, match="already been resolved"):
        orchestrator.approve_action(action_id)

# 4. Email draft generator uses RAG (LLM-based)
@skip_no_groq
def test_email_draft_generator_uses_rag(clean_env):
    orchestrator = MCPOrchestrator(db_path=TEST_DB_PATH)
    
    payload = {
        "recipient": "client@example.com",
        "subject": "Parag Parikh Liquid Fund exit load query",
        "topic": "exit load for Parag Parikh Liquid Fund"
    }
    action_id = orchestrator.queue_action("Email Draft Generator", payload)
    
    # Execute action via approval
    result = orchestrator.approve_action(action_id)
    assert result["status"] == "success"
    assert "draft" in result
    
    # Assert RAG context snippet was retrieved (e.g. exit load values appear in the email)
    # The exit load for Parag Parikh Liquid Fund is 0.0075% on day 1, etc.
    email_draft = result["draft"]
    assert "client@example.com" not in email_draft  # recipient is in payload, body is text
    assert "Parag Parikh" in email_draft
    # Since exit load involves percentages or days or "liquid", check for those
    assert "load" in email_draft.lower() or "exit" in email_draft.lower()

# 5. Calendar hold creator test
def test_calendar_hold_creator(clean_env):
    orchestrator = MCPOrchestrator(db_path=TEST_DB_PATH)
    
    payload = {
        "title": "Quarterly Review",
        "start_time": "Friday 2:00 PM",
        "duration_minutes": 45,
        "attendees": ["advisor@kuvera.in", "client@example.com"]
    }
    action_id = orchestrator.queue_action("Calendar Hold Creator", payload)
    
    # Assert not executed
    assert orchestrator.persistence.get("calendar_holds") is None
    
    # Approve and execute
    result = orchestrator.approve_action(action_id)
    assert result["status"] == "success"
    
    # Assert execution did create the calendar hold
    holds = orchestrator.persistence.get("calendar_holds")
    assert holds is not None
    assert len(holds) == 1
    assert holds[0]["title"] == "Quarterly Review"
    assert holds[0]["start_time"] == "Friday 2:00 PM"
    assert holds[0]["duration_minutes"] == 45
    assert holds[0]["attendees"] == ["advisor@kuvera.in", "client@example.com"]
