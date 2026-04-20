from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from tax_engine import TaxEngine
from nlp_engine import NLPEngine

app = FastAPI(title="Tax Assist AI - Deep Consultant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

nlp = NLPEngine()
engine = TaxEngine()

class ChatRequest(BaseModel):
    message: str
    session: Dict[str, Any]

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return nlp.process_message(request.message, request.session)

@app.post("/calculate")
async def calculate_endpoint(data: Dict[str, Any]):
    # Pre-process capital gains if they exist in session
    cg_list = []
    if "equity_ltcg" in data:
        cg_list.append({"type": "equity_ltcg", "amount": data["equity_ltcg"]})
    if "equity_stcg" in data:
        cg_list.append({"type": "equity_stcg", "amount": data["equity_stcg"]})
    
    calc_data = {
        "salary": data.get("salary", 0),
        "business": data.get("business", 0),
        "agriculture": data.get("agriculture", 0),
        "rental": data.get("rental", 0),
        "other_income": data.get("other_income", 0),
        "capital_gains": cg_list,
        "80c": data.get("80c", 0),
        "80d": data.get("80d", 0),
        "80d_parents": data.get("80d_parents", 0),
        "80e": data.get("80e", 0),
        "80g": data.get("80g", 0),
        "hra": data.get("hra", 0)
    }
    
    results = engine.calculate_tax_advanced(calc_data)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
