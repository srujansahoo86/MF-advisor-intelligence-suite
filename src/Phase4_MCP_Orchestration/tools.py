import os
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine

def doc_append(file_path: str, content: str) -> dict:
    """Appends content to a specified text file."""
    # Ensure directory exists
    dir_name = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(dir_name, exist_ok=True)
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content + "\n")
        
    return {
        "status": "success",
        "message": f"Appended content to {file_path}"
    }

def calendar_hold_creator(persistence: Persistence, title: str, start_time: str, duration_minutes: int, attendees: list[str]) -> dict:
    """Saves calendar hold parameters to SQLite persistence."""
    holds = persistence.get("calendar_holds")
    if not holds or not isinstance(holds, list):
        holds = []
        
    new_hold = {
        "title": title,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "attendees": attendees
    }
    holds.append(new_hold)
    persistence.set("calendar_holds", holds)
    
    return {
        "status": "success",
        "message": f"Calendar hold '{title}' scheduled for {start_time}"
    }

def email_draft_generator(persistence: Persistence, recipient: str, subject: str, topic: str) -> dict:
    """Queries Phase 1 RAG engine for topic context and drafts an advisor email."""
    # 1. Query Phase 1 RAG Engine for context snippet
    try:
        rag = RAGEngine()
        # Query specifically for advisor email context on the topic
        query = f"Provide a brief, factual summary of {topic} for an advisor email."
        answer = rag.answer_query(query)
        if answer and answer.text and "verified source for that" not in answer.text:
            context_snippet = answer.text
        else:
            context_snippet = f"General advisor query topic: {topic}."
    except Exception:
        context_snippet = f"General advisor query topic: {topic}."

    # 2. Compose the email body
    email_body = (
        f"Dear Client,\n\n"
        f"Regarding your inquiry about {topic}:\n"
        f"{context_snippet}\n\n"
        f"Please let me know if you would like to discuss this further during our call.\n\n"
        f"Best regards,\n"
        f"Mutual Fund Advisor"
    )

    draft = {
        "recipient": recipient,
        "subject": subject,
        "body": email_body
    }
    
    # 3. Persist the draft to the database
    persistence.set("latest_email_draft", draft)
    
    return {
        "status": "success",
        "draft": email_body
    }
