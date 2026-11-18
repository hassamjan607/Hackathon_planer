"""
planner.trace
First-class trace collector.
Numbers model calls globally across the session (CALL #1, CALL #2, ...).
Logs separate UN-NUMBERED events:
  SUPERSEDE, NOISE, ASK, RULE, REPAIR, ACCEPT, REJECT, CHECK, NOTE.
Maintains per-run and cumulative token statistics.
Enforces hard limit of 5 calls per update run (raises error on call 6).
Renders formatted text and JSON.
"""

import json
import os
from typing import List, Dict, Any, Optional

OUT_DIR = "out"
TRACE_TXT_FILE = os.path.join(OUT_DIR, "trace.txt")
TRACE_JSON_FILE = os.path.join(OUT_DIR, "trace.json")

class CallLimitExceededError(RuntimeError):
    """Raised when an update run exceeds the maximum allowed model calls."""
    pass

class Trace:
    def __init__(self, run_no: int, mode: str, deadline: float, start_call_no: int = 1):
        self.run_no = run_no
        self.mode = mode
        self.deadline = deadline
        self.current_call_no = start_call_no
        self.calls: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    def record_call(
        self,
        model: str,
        area: str,
        in_tokens: Optional[int],
        out_tokens: Optional[int],
        total_tokens: Optional[int],
        input_text: str,
        output_text: str,
        ms: float
    ) -> int:
        """
        Record a numbered model call.
        Enforces: max 5 calls on UPDATE mode.
        """
        if self.mode == "UPDATE" and len(self.calls) >= 5:
            raise CallLimitExceededError(
                f"Update run exceeded hard limit of 5 model calls (attempted call {len(self.calls) + 1})."
            )

        call_id = self.current_call_no
        call_entry = {
            "n": call_id,
            "model": model,
            "area": area,
            "in": in_tokens,
            "out": out_tokens,
            "total": total_tokens,
            "input": input_text,
            "output": output_text,
            "ms": ms
        }
        self.calls.append(call_entry)
        self.current_call_no += 1
        return call_id

    def event(self, event_type: str, msg_ref: Any = None, text: str = "", **kwargs) -> None:
        """Log an un-numbered domain event (SUPERSEDE, NOISE, ASK, REPAIR, ACCEPT, REJECT, CHECK, NOTE)."""
        ev = {
            "type": event_type.upper(),
            "msg": msg_ref,
            "text": text,
            **kwargs
        }
        self.events.append(ev)

    def run_totals(self) -> Dict[str, Any]:
        """Compute token totals for this specific run."""
        calls_count = len(self.calls)
        in_sum = sum(c["in"] for c in self.calls if c["in"] is not None)
        out_sum = sum(c["out"] for c in self.calls if c["out"] is not None)
        total_sum = sum(c["total"] for c in self.calls if c["total"] is not None)
        return {
            "calls": calls_count,
            "in": in_sum if in_sum > 0 or calls_count == 0 else None,
            "out": out_sum if out_sum > 0 or calls_count == 0 else None,
            "total": total_sum if total_sum > 0 or calls_count == 0 else None
        }

    def format_text(self, new_desc: str = "") -> str:
        """Format the trace text for this run exactly per guide specification."""
        lines = []
        if self.mode == "FULL":
            lines.append(f"=== RUN {self.run_no} (FULL) ===")
        elif self.mode == "UPDATE":
            desc = f" new: {new_desc}" if new_desc else ""
            lines.append(f"=== RUN {self.run_no} (UPDATE) ==={desc}")
        else:
            lines.append(f"=== RUN {self.run_no} ({self.mode}) ===")

        # Interleave calls and events chronologically if desired, or print calls then events
        for c in self.calls:
            in_fmt = c["in"] if c["in"] is not None else "not reported"
            out_fmt = c["out"] if c["out"] is not None else "not reported"
            tot_fmt = c["total"] if c["total"] is not None else "not reported"
            sec = round(c["ms"] / 1000.0, 1)
            lines.append(
                f"CALL #{c['n']} model={c['model']} area={c['area']} "
                f"tokens in={in_fmt} out={out_fmt} total={tot_fmt} ({sec} s)"
            )
            lines.append(f" INPUT : {c['input']}")
            lines.append(f" OUTPUT: {c['output']}")

        for ev in self.events:
            ev_type = ev["type"]
            msg_str = f"msg#{ev['msg']}: " if ev.get("msg") is not None else ""
            txt = ev.get("text", "")
            lines.append(f"{ev_type} {msg_str}{txt}".strip())

        tot = self.run_totals()
        in_str = tot["in"] if tot["in"] is not None else "not reported"
        out_str = tot["out"] if tot["out"] is not None else "not reported"
        tot_str = tot["total"] if tot["total"] is not None else "not reported"
        lines.append(f"TOTAL TOKENS run {self.run_no}: calls={tot['calls']} in={in_str} out={out_str} total={tot_str}")
        return "\n".join(lines)


def append_cumulative_trace(run_trace_text: str, cumulative_totals: Optional[Dict[str, Any]] = None, path: str = TRACE_TXT_FILE) -> None:
    """Append current run trace to cumulative out/trace.txt."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    with open(path, "a", encoding="utf-8") as f:
        f.write(run_trace_text.strip() + "\n\n")
        if cumulative_totals:
            tot_calls = cumulative_totals.get("calls", 0)
            tot_tokens = cumulative_totals.get("total", 0)
            f.write(f"TOTAL TOKENS (all runs): calls={tot_calls} total={tot_tokens}\n\n")

def update_trace_json(run_data: Dict[str, Any], path: str = TRACE_JSON_FILE) -> None:
    """Save/update cumulative out/trace.json for UI rendering."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    data = {"runs": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"runs": []}

    data["runs"].append(run_data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
