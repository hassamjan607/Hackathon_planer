"""
planner.state
Atomic JSON persistence for state/state.json.
Holds message history, message statuses, facts, last plan, run history, and hashes.
Uses temporary file and atomic rename to prevent corruption on crash or timeout.
"""

import json
import os
import tempfile
from typing import Optional, Dict, Any, List

STATE_DIR = "state"
STATE_FILE = os.path.join(STATE_DIR, "state.json")

class State:
    def __init__(
        self,
        hashes: Optional[List[str]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        facts: Optional[Dict[str, Any]] = None,
        plan: Optional[Dict[str, Any]] = None,
        runs: Optional[List[Dict[str, Any]]] = None,
        keys: Optional[List[str]] = None
    ):
        self.hashes: List[str] = hashes or []
        self.messages: List[Dict[str, Any]] = messages or []
        self.facts: Dict[str, Any] = facts or {}
        self.plan: Optional[Dict[str, Any]] = plan
        self.runs: List[Dict[str, Any]] = runs or []
        self.keys: List[str] = keys or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "hashes": self.hashes,
            "messages": self.messages,
            "facts": self.facts,
            "plan": self.plan,
            "runs": self.runs,
            "keys": self.keys
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "State":
        return cls(
            hashes=data.get("hashes", []),
            messages=data.get("messages", []),
            facts=data.get("facts", {}),
            plan=data.get("plan"),
            runs=data.get("runs", []),
            keys=data.get("keys", [])
        )

def load(state_path: str = STATE_FILE) -> Optional[State]:
    """Load persisted state if present; returns None if file doesn't exist or is invalid."""
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return State.from_dict(data)
    except Exception:
        return None

def save(state: State, state_path: str = STATE_FILE) -> None:
    """Atomically save state to disk using a temp file and rename."""
    directory = os.path.dirname(state_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    data = state.to_dict()
    temp_fd, temp_path = tempfile.mkstemp(dir=directory, prefix="state_", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # On Windows, os.replace replaces atomically if target exists
        os.replace(temp_path, state_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
