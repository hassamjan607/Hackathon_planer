"""
planner.cli
Command line interface, argument handling, mode detection, and top-level flow.
Enforces deadlines, prints traces even on failure, and keeps last valid plan.
"""

import os
import sys
import shutil
from typing import List, Optional

from planner import ingest, state as state_mod, engine
from planner.trace import Trace, append_cumulative_trace, update_trace_json, TRACE_TXT_FILE, TRACE_JSON_FILE
from planner.render import terminal, html

# Defaults
DEFAULT_MESSAGES_FILE = "messages.txt"
FULL_TIMEOUT = 120.0
UPDATE_TIMEOUT = 60.0

def detect_mode(msgs: list, state: Optional[state_mod.State]) -> tuple[str, list, list]:
    """
    Decide mode:
      - If state is None -> FULL, all messages
      - If state exists:
          known = set(state.hashes)
          new = [m for m in msgs if m.hash not in known]
          overlap = len(msgs) - len(new)
          If overlap == 0 and len(msgs) >= 5: FULL (fresh pack: reset/archive state)
          Elif not new: NOOP
          Else: UPDATE (only new messages)
    Returns: (mode, messages_to_process, new_messages_list)
    """
    if state is None:
        return "FULL", msgs, msgs

    known_hashes = set(state.hashes)
    new_msgs = [m for m in msgs if m["hash"] not in known_hashes]
    overlap = len(msgs) - len(new_msgs)

    if overlap == 0 and len(msgs) >= 5:
        # Fresh pack detected! Reset runtime state to prevent stale state corruption
        return "FULL", msgs, msgs
    elif not new_msgs:
        return "NOOP", [], []
    else:
        return "UPDATE", new_msgs, new_msgs

def run_cli(argv: Optional[List[str]] = None) -> int:
    """Core CLI execution logic."""
    if argv is None:
        argv = sys.argv[1:]

    # One command: positional path if provided, else messages.txt
    file_path = argv[0] if len(argv) > 0 else DEFAULT_MESSAGES_FILE
    
    if not os.path.exists(file_path):
        print(f"Error: Message file not found: {file_path}", file=sys.stderr)
        return 1

    # Ingest messages untouched
    curr_state = state_mod.load()
    start_idx = 1
    if curr_state and curr_state.messages:
        start_idx = max(m.get("n", 0) for m in curr_state.messages) + 1

    msgs = ingest.read_messages(file_path, start_index=start_idx)
    mode, to_process, new_msgs = detect_mode(msgs, curr_state)

    # Determine run number and starting call number
    run_no = 1
    start_call_no = 1
    if mode == "FULL":
        # Clear out/trace.txt on fresh pack full run
        if os.path.exists(TRACE_TXT_FILE):
            try:
                os.remove(TRACE_TXT_FILE)
            except Exception:
                pass
        if os.path.exists(TRACE_JSON_FILE):
            try:
                os.remove(TRACE_JSON_FILE)
            except Exception:
                pass
    elif curr_state:
        run_no = len(curr_state.runs) + 1
        # Calculate global call number offset across past runs
        total_past_calls = sum(r.get("calls", 0) for r in curr_state.runs)
        start_call_no = total_past_calls + 1

    deadline = FULL_TIMEOUT if mode == "FULL" else UPDATE_TIMEOUT
    trace = Trace(run_no=run_no, mode=mode, deadline=deadline, start_call_no=start_call_no)

    if mode == "NOOP":
        # Nothing new: reprint last plan, 0 calls
        trace.event("NOTE", text="No new messages detected; re-displaying last plan.")
        if curr_state and curr_state.plan:
            terminal.render_terminal(None, trace)
        else:
            print("No plan currently available in state.")
        return 0

    try:
        result = engine.run(mode=mode, messages=to_process, state=curr_state, trace=trace)
        
        # Terminal render
        terminal.render_terminal(result, trace)
        
        # File outputs
        html.render_html(result, trace)
        
        # Save trace cumulative
        run_text = trace.format_text(new_desc=f"msg#{new_msgs[0]['n']}" if new_msgs else "")
        cumulative_totals = None
        if result.state:
            # Aggregate totals across all runs
            cum_calls = sum(r.get("calls", 0) for r in result.state.runs) + len(trace.calls)
            cum_tokens = sum(r.get("tokens", 0) for r in result.state.runs) + (trace.run_totals().get("total") or 0)
            cumulative_totals = {"calls": cum_calls, "total": cum_tokens}
            
            # Record this run into state
            result.state.runs.append({
                "run_no": run_no,
                "mode": mode,
                "calls": len(trace.calls),
                "tokens": trace.run_totals().get("total") or 0
            })
            state_mod.save(result.state)

        append_cumulative_trace(run_text, cumulative_totals)
        return 0

    except Exception as e:
        # Always print trace even on error or timeout
        print(trace.format_text(), file=sys.stderr)
        print(f"\nExecution failed with error: {e}", file=sys.stderr)
        return 1

def main(argv: Optional[List[str]] = None) -> int:
    return run_cli(argv)

if __name__ == "__main__":
    sys.exit(main())
