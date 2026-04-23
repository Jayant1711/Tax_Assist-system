from fastapi import FastAPI, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from tax_engine import TaxEngine
from nlp_engine import NLPEngine
from audit_logger import AuditLogger
from session_lab import SessionLab
import uvicorn
import os
import json

app = FastAPI(title="Tax Assist AI - Deep Consultant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

nlp = NLPEngine()
engine = TaxEngine()
audit = AuditLogger()
lab = SessionLab()

class ChatRequest(BaseModel):
    message: str
    session: Dict[str, Any]

def clean_json(obj):
    if hasattr(obj, "__dict__"): return clean_json(obj.__dict__)
    if isinstance(obj, dict): return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_json(i) for i in obj]
    if hasattr(obj, "item"): return obj.item() # numpy handle
    return obj

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    # 1. Process Message
    result = nlp.process_message(request.message, request.session)
    
    # 2. Real-time Calculation (Insights)
    tax_result = None
    if result["session"].get("salary", 0) > 0 or result["session"].get("business", 0) > 0:
        try:
            tax_result = engine.calculate_tax_advanced(result["session"])
        except Exception as e:
            print(f"Calculation Error: {e}")

    # 3. Schedule Background Audit Log
    sid = request.session.get("id", "default")
    background_tasks.add_task(
        audit.log_interaction,
        session_id=sid,
        input_text=request.message,
        response=result["response"],
        session_state=result["session"],
        tax_results=tax_result
    )
    
    # 4. Record to Industrial Black Box for Regression Auditing
    lab.record_turn(sid, {
        "input": request.message,
        "response": result["response"],
        "extracted": result.get("extracted"),
        "plan": result.get("plan"),
        "state": result["session"],
        "audit": tax_result
    })
    
    # Return everything for the frontend to render real-time
    return clean_json({**result, "tax_report": tax_result})

@app.get("/history/{sid}")
async def get_history(sid: str):
    log_file = "logs/session_audit.json"
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            logs = json.load(f)
        session_logs = [l for l in logs if l.get("session_id") == sid]
        return session_logs
    except:
        return []

@app.post("/calculate")
async def calculate_endpoint(data: Dict[str, Any]):
    # Maintain existing calculator endpoint for the UI
    results = engine.calculate_tax_advanced(data)
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
