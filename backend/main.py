from fastapi import FastAPI, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from tax_engine import TaxEngine
from nlp_engine import NLPEngine
from audit_logger import AuditLogger
import uvicorn
import os
import json

app = FastAPI(title="Tax Assist AI - Deep Consultant")

# Permissive CORS for Local Development
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

class ChatRequest(BaseModel):
    message: str
    session: Dict[str, Any]

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    # 1. Process Message
    result = nlp.process_message(request.message, request.session)
    
    # 2. Prepare Audit Data (Calculate tax if needed)
    tax_result = None
    if result["session"].get("phase") == "FINAL":
        tax_result = engine.calculate_tax_advanced(result["session"])
    
    # 3. Schedule Background Audit Log
    background_tasks.add_task(
        audit.log_interaction,
        session_id=request.session.get("id", "default"),
        input_text=request.message,
        response=result["response"],
        session_state=result["session"],
        tax_results=tax_result
    )
    
    return result

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
