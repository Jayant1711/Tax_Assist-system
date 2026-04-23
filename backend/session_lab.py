import json
import os
from datetime import datetime
from typing import Dict, Any

class SessionLab:
    """
    The Industrial Black Box — Records every neuron fire in the system.
    Designed for large-scale audit and regression solving.
    """
    def __init__(self, lab_dir: str = "logs/blackbox"):
        self.lab_dir = lab_dir
        if not os.path.exists(self.lab_dir):
            os.makedirs(self.lab_dir)

    def record_turn(self, session_id: str, turn_data: Dict[str, Any]):
        """
        Appends a high-fidelity turn to the session's blackbox file.
        """
        try:
            file_path = os.path.join(self.lab_dir, f"{session_id}.json")
            
            # Load existing or start new
            data = {"session_id": session_id, "turns": [], "final_audit": None}
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            # Add the turn
            turn_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_input": turn_data.get("input"),
                "nlp_extraction": turn_data.get("extracted"),
                "agent_plan": turn_data.get("plan"),
                "ai_response": turn_data.get("response"),
                "state_snapshot": self._safe_state(turn_data.get("state", {}))
            }
            data["turns"].append(turn_entry)
            
            # If it's a final audit, store it
            if turn_data.get("audit"):
                data["final_audit"] = turn_data.get("audit")

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"[BlackBox Error] {e}")

    def _safe_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prevents logging massive history blobs in every turn."""
        return {k: v for k, v in state.items() if k not in ["history", "id"]}

if __name__ == "__main__":
    # Small test
    lab = SessionLab()
    lab.record_step("test_01", {"input": "Hello", "response": "Hi", "state": {"test": True}})
    print("Step recorded in logs/lab/test_01_lab.jsonl")
