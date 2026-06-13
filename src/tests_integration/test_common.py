import pytest
from src.Phase0_Shared_Foundation.schemas import Answer, PendingAction
from src.Phase0_Shared_Foundation.guardrails import Guardrails
from src.Phase0_Shared_Foundation.pii import redact_pii
from src.Phase0_Shared_Foundation.persistence import Persistence
import os

def test_schema_roundtrip():
    ans = Answer(text="Test", citation_links=["http://test.com"])
    assert ans.is_safe == True
    
    ans_dict = ans.model_dump()
    ans_reloaded = Answer(**ans_dict)
    assert ans_reloaded.text == "Test"

def test_guardrails():
    # Should refuse investment advice
    is_safe, msg = Guardrails.check_query("Should I invest in Kuvera ELSS?")
    assert is_safe == False
    assert "AMFI" in msg
    
    # Should refuse performance claims
    is_safe, msg = Guardrails.check_query("Will this fund double my money?")
    assert is_safe == False
    assert "performance" in msg
    
    # Should pass factual query
    is_safe, msg = Guardrails.check_query("What is the exit load for Parag Parikh Flexi Cap?")
    assert is_safe == True

def test_pii_redaction():
    # Email
    text_email = "My email is user@example.com, please reply."
    redacted = redact_pii(text_email)
    assert "user@example.com" not in redacted
    assert "[EMAIL_REDACTED]" in redacted

    # 10-digit Indian mobile
    text_phone = "Call me on 9876543210 for details."
    redacted = redact_pii(text_phone)
    assert "9876543210" not in redacted
    assert "[PHONE_REDACTED]" in redacted

    # +91-prefixed phone (new pattern — covers R017 in reviews.csv)
    text_phone_91 = "Reach me at +91 98765 43210 anytime."
    redacted = redact_pii(text_phone_91)
    assert "+91 98765 43210" not in redacted
    assert "[PHONE_REDACTED]" in redacted

    # Indian PAN card (new explicit pattern — covers R010)
    text_pan = "My PAN is ABCDE1234F for KYC verification."
    redacted = redact_pii(text_pan)
    assert "ABCDE1234F" not in redacted
    assert "[PAN_REDACTED]" in redacted

    # Folio number (new explicit pattern — covers R028)
    text_folio = "Folio number 1234567/89 shows wrong balance."
    redacted = redact_pii(text_folio)
    assert "1234567/89" not in redacted
    assert "[FOLIO_REDACTED]" in redacted

def test_persistence():
    db_path = "./data/test.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    p = Persistence(db_path)
    
    # Test general store
    p.set("test_key", {"data": "value"})
    res = p.get("test_key")
    assert res["data"] == "value"
    
    # Test approval queue
    action = PendingAction(action_id="123", tool_name="Doc Append", payload={"test": 1})
    p.add_pending_action(action)
    
    pending = p.get_pending_actions()
    assert len(pending) == 1
    assert pending[0].action_id == "123"
    
    p.update_action_status("123", "APPROVED")
    pending_after = p.get_pending_actions()
    assert len(pending_after) == 0
    
    if os.path.exists(db_path):
        os.remove(db_path)
