import os
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import Answer, PendingAction
from src.Phase1_FAQ_Chatbot.rag_engine import get_rag_engine
from src.Phase3_Voice_Scheduler.voice_adapter import VoiceAdapter, AgentResponse
from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator

app = FastAPI(title="MF Advisor Intelligence Suite API")

# Enable CORS for local UI files to make requests without cross-origin issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class TranscriptRequest(BaseModel):
    transcript: str

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ui_path = os.path.join(base_dir, "stitch_mf_advisor_intelligence_suite", "code.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        alt_path = "stitch_mf_advisor_intelligence_suite/code.html"
        if os.path.exists(alt_path):
            with open(alt_path, "r", encoding="utf-8") as f:
                return f.read()
    raise HTTPException(status_code=404, detail="Dashboard UI file not found.")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/faq", response_model=Answer)
def get_faq_answer(req: QueryRequest):
    try:
        rag = get_rag_engine()
        return rag.answer_query(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pulse")
def get_weekly_pulse():
    try:
        persistence = Persistence()
        pulse = persistence.get("latest_pulse")
        if not pulse:
            # Generate dynamically from reviews.csv if database store is empty
            csv_path = Config.REVIEWS_CSV_PATH
            if os.path.exists(csv_path):
                from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
                from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator
                
                processor = ReviewProcessor(csv_path)
                reviews = processor.load()
                gen = PulseGenerator()
                pulse_obj = gen.generate(reviews)
                pulse = pulse_obj.model_dump()
            else:
                pulse = {
                    "top_themes": [
                        {"theme_name": "Direct Plans Conversion", "description": "Many clients asking to switch regular funds to direct."}
                    ],
                    "user_quotes": ["How do I switch my regular mutual funds to direct?"],
                    "key_observation": "No reviews found in DB or CSV, loaded fallback mock pulse.",
                    "action_ideas": [
                        "Create a one-click regular-to-direct switch button.",
                        "Publish an educational infographic comparing Regular vs Direct TER fees.",
                        "Add exit load tooltips inside the customer portfolio view."
                    ],
                    "word_count": 60
                }
        return pulse
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fee-explainer")
def get_fee_explainer():
    try:
        persistence = Persistence()
        explainer = persistence.get("latest_fee_explainer")
        if not explainer:
            # Generate dynamically from reviews.csv if database store is empty,
            # and refresh the FAQ retrieval corpus (M2 -> M1 refresh mechanism)
            csv_path = Config.REVIEWS_CSV_PATH
            if os.path.exists(csv_path):
                from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
                from src.Phase2_Review_Intelligence.fee_explainer import FeeExplainerGenerator
                from src.Phase2_Review_Intelligence.corpus_updater import CorpusUpdater

                processor = ReviewProcessor(csv_path)
                reviews = processor.load()
                gen = FeeExplainerGenerator()
                explainer_obj = gen.generate(reviews)
                explainer = explainer_obj.model_dump()

                CorpusUpdater().add_fee_explainer(explainer_obj)
            else:
                explainer = {
                    "bullets": [
                        "Expense ratio (TER) is the annual fee a fund charges to cover management and operating costs.",
                        "Direct plans have a lower expense ratio than regular plans because they cut out distributor commission.",
                        "Exit load is a fee charged if you redeem units before a scheme's minimum holding period.",
                        "Stamp duty of 0.005% is deducted from every mutual fund purchase, including SIP instalments.",
                        "ELSS and other lock-in funds restrict withdrawals until the lock-in period ends.",
                        "A lower expense ratio means more of your returns stay invested and compound over time."
                    ],
                    "source_links": [
                        Config.FEE_EXPLAINER_AMFI_URL,
                        Config.FEE_EXPLAINER_SEBI_URL,
                    ],
                    "last_checked": f"Last checked: {date.today().isoformat()}"
                }
        return explainer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sources")
def get_sources():
    return {"sources": sorted(Config.SOURCE_MANIFEST_URLS)}

@app.post("/api/voice")
def process_voice_transcript(req: TranscriptRequest):
    try:
        adapter = VoiceAdapter()
        res = adapter.process(req.transcript)
        # Convert dataclass/dict to response dict
        return {
            "message": res.message,
            "booking": res.booking.model_dump() if res.booking else None,
            "booking_code": res.booking_code,
            "top_theme": res.top_theme,
            "awaiting_response": res.awaiting_response,
            "session_ended": res.session_ended
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/actions/pending", response_model=List[PendingAction])
def get_pending_actions():
    try:
        orchestrator = MCPOrchestrator()
        return orchestrator.list_pending()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/approve/{action_id}")
def approve_pending_action(action_id: str):
    try:
        orchestrator = MCPOrchestrator()
        result = orchestrator.approve_action(action_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/reject/{action_id}")
def reject_pending_action(action_id: str):
    try:
        orchestrator = MCPOrchestrator()
        result = orchestrator.reject_action(action_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
