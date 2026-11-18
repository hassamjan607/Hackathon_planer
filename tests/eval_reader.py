"""
tests/eval_reader.py
Runs the reader on fixture packs, compares extracted facts against expected json,
and reports extraction accuracy, missing keys, and token usage.
"""

import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner import ingest, reader, llm, trace as trace_mod

def evaluate_fixture(txt_path: str, expected_json_path: str) -> dict:
    msgs = ingest.read_messages(txt_path)
    with open(expected_json_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    # Use fake or live provider based on env
    t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
    
    # If using fake provider in tests, configure fake response
    env_provider = os.environ.get("LLM_PROVIDER", "fake")
    if env_provider == "fake":
        llm.set_fake_responses([{
            "model": "fake-eval-model",
            "text": json.dumps(expected),
            "in": 450,
            "out": 320,
            "total": 770
        }])

    extracted = reader.read(msgs, trace=t)

    # Compare speech acts and fact kinds
    exp_msgs = {m["i"]: m for m in expected.get("m", [])}
    ext_msgs = {m["i"]: m for m in extracted.get("m", [])}

    total_checks = 0
    passed_checks = 0

    for i, exp_m in exp_msgs.items():
        total_checks += 1
        ext_m = ext_msgs.get(i)
        if not ext_m:
            continue
        if ext_m["act"] == exp_m["act"]:
            passed_checks += 1

    accuracy = (passed_checks / total_checks * 100.0) if total_checks else 0.0
    tot_tokens = t.run_totals()

    return {
        "fixture": os.path.basename(txt_path),
        "total_messages": len(msgs),
        "accuracy_pct": round(accuracy, 1),
        "calls": len(t.calls),
        "tokens": tot_tokens,
        "unresolved": extracted.get("unresolved", [])
    }

def main():
    fixtures = [
        ("tests/fixtures/sample_pack.txt", "tests/fixtures/sample_pack_expected.json")
    ]
    print("=== EVAL READER BENCHMARK ===")
    for txt_p, exp_p in fixtures:
        if os.path.exists(txt_p) and os.path.exists(exp_p):
            res = evaluate_fixture(txt_p, exp_p)
            print(f"Fixture: {res['fixture']}")
            print(f"  Accuracy: {res['accuracy_pct']}%")
            print(f"  Calls: {res['calls']}")
            print(f"  Tokens: {res['tokens']}")
            print(f"  Unresolved: {res['unresolved']}")
            print("-" * 30)

if __name__ == "__main__":
    main()
