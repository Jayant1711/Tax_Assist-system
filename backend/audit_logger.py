import json
import os
from datetime import datetime
from typing import Dict, Any

class AuditLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        self.log_file = os.path.join(self.log_dir, "session_audit.json")

    def log_interaction(self, session_id: str, input_text: str, response: str, session_state: Dict[str, Any], tax_results: Any = None):
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "user_input": input_text,
                "ai_response": response,
                "internal_state": self._safe_serialize(session_state),
                "tax_calculation": self._serialize_tax(tax_results) if tax_results else "Pending"
            }
            
            logs = []
            if os.path.exists(self.log_file):
                try:
                    with open(self.log_file, "r") as f:
                        logs = json.load(f)
                except: logs = []
                
            logs.append(log_entry)
            with open(self.log_file, "w") as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            print(f"Audit Log Error: {e}")

    def _safe_serialize(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._safe_serialize(v) for k, v in obj.items() if k != "memory"}
        if isinstance(obj, list):
            return [self._safe_serialize(i) for i in obj]
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        return str(obj)

    def _serialize_tax(self, results: Dict[str, Any]) -> Dict[str, Any]:
        serialized = {}
        for regime, data in results.items():
            if isinstance(data, (str, float, int)): 
                serialized[regime] = data
                continue
            try:
                serialized[regime] = {
                    "total_tax": float(getattr(data, 'total_tax', 0)),
                    "taxable_income": float(getattr(data, 'taxable_income', 0)),
                    "efficiency": float(getattr(data, 'efficiency_score', 0))
                }
            except: serialized[regime] = str(data)
        return serialized
