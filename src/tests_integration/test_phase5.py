import os
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.Phase0_Shared_Foundation.config import Config

TEST_DB_PATH = "./data/test_phase5.db"
TEST_APPEND_FILE = "./data/test_append_phase5.txt"

@pytest.fixture
def clean_env():
    # Point configuration path to test DB for security
    old_db = Config.SQLITE_DB_PATH
    Config.SQLITE_DB_PATH = TEST_DB_PATH
    
    for path in [TEST_DB_PATH, TEST_APPEND_FILE]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    
    yield TestClient(app)
    
    # Clean up
    for path in [TEST_DB_PATH, TEST_APPEND_FILE]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    Config.SQLITE_DB_PATH = old_db

has_groq_key = bool(os.getenv("GROQ_API_KEY"))
skip_no_groq = pytest.mark.skipif(not has_groq_key, reason="GROQ_API_KEY environment variable not set")

# 1. Root route serves dashboard
def test_api_root(clean_env):
    client = clean_env
    res = client.get("/")
    assert res.status_code == 200
    assert "FINTELLIGENCE" in res.text

# 2. Health check
def test_api_health(clean_env):
    client = clean_env
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}

# 2. Pulse check (always runs, falls back to reviews.csv or mock)
def test_api_pulse(clean_env):
    client = clean_env
    res = client.get("/api/pulse")
    assert res.status_code == 200
    data = res.json()
    assert "top_themes" in data
    assert "user_quotes" in data
    assert "action_ideas" in data

# 3. FAQ check (LLM-based)
@skip_no_groq
def test_api_faq(clean_env):
    client = clean_env
    res = client.post("/api/faq", json={"query": "What is the exit load for Parag Parikh Liquid Fund?"})
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "citation_links" in data
    assert data["is_safe"] is True

# 4. Voice scheduling check (LLM-based)
@skip_no_groq
def test_api_voice_booking(clean_env):
    client = clean_env
    
    # Set a mock latest_pulse
    from src.Phase0_Shared_Foundation.persistence import Persistence
    p = Persistence(TEST_DB_PATH)
    p.set("latest_pulse", {
        "top_themes": [{"theme_name": "Direct Plans Conversion", "description": ""}],
        "user_quotes": [],
        "key_observation": "",
        "action_ideas": [],
        "word_count": 0
    })

    res = client.post("/api/voice", json={"transcript": "Book an appointment on Friday afternoon about Exit Load"})
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert "booking" in data
    assert data["booking"] is not None
    assert data["booking_code"] is not None
    assert "Direct Plans Conversion" in data["message"]

# 5. Actions management check
def test_api_actions_flow(clean_env):
    client = clean_env
    
    # Queue an action directly in SQLite via MCPOrchestrator to test REST routes
    from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator
    orchestrator = MCPOrchestrator(TEST_DB_PATH)
    
    payload = {
        "file_path": TEST_APPEND_FILE,
        "content": "Line content"
    }
    action_id = orchestrator.queue_action("Doc Append", payload)
    
    # 1. GET pending Actions
    res_list = client.get("/api/actions/pending")
    assert res_list.status_code == 200
    actions = res_list.json()
    assert len(actions) == 1
    assert actions[0]["action_id"] == action_id
    assert actions[0]["tool_name"] == "Doc Append"
    
    # 2. POST approve Action
    assert not os.path.exists(TEST_APPEND_FILE)
    res_app = client.post(f"/api/actions/approve/{action_id}")
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "success"
    
    # Verify execution side effect
    assert os.path.exists(TEST_APPEND_FILE)
    
    # 3. Verify it is no longer pending
    res_list_2 = client.get("/api/actions/pending")
    assert len(res_list_2.json()) == 0
    
    # 4. POST reject on resolved action should fail (400)
    res_rej = client.post(f"/api/actions/reject/{action_id}")
    assert res_rej.status_code == 400

# 6. Sources manifest check
def test_api_sources(clean_env):
    client = clean_env
    res = client.get("/api/sources")
    assert res.status_code == 200
    data = res.json()
    assert "sources" in data
    assert len(data["sources"]) >= 30
    assert all(u.startswith("http") for u in data["sources"])

# 7. Fee Explainer endpoint check (M2 -> M1 refresh mechanism)
def test_api_fee_explainer(clean_env):
    client = clean_env
    res = client.get("/api/fee-explainer")
    assert res.status_code == 200
    data = res.json()
    assert len(data["bullets"]) == 6
    assert len(data["source_links"]) == 2
    assert all(u.startswith("http") for u in data["source_links"])
    assert data["last_checked"].startswith("Last checked: ")
