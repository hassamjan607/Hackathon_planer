"""
planner.render.html
Writes self-contained out/report.html by inlining CSS, JS, and JSON data.
Zero external CDN dependencies, fully offline file:// compatible.
Also writes out/plan.json.
"""

import json
import os
from typing import Any

OUT_DIR = "out"
PLAN_JSON_FILE = os.path.join(OUT_DIR, "plan.json")
REPORT_HTML_FILE = os.path.join(OUT_DIR, "report.html")

def render_html(result: Any, trace: Any, out_path: str = REPORT_HTML_FILE) -> str:
    """Generate and write self-contained out/report.html and out/plan.json."""
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR, exist_ok=True)

    plan = getattr(result, "plan", {}) or {}
    checks = getattr(result, "checks", []) or []
    unresolved = getattr(result, "unresolved", []) or []
    parsed_msgs = getattr(result, "parsed_messages", []) or []

    # Map message statuses for display
    # (used, superseded, noise, request, rejected)
    msg_entries = []
    rej_texts = [e.get("text", "") for e in trace.events if e.get("type") == "REJECT"]
    
    for m in parsed_msgs:
        i = m.get("i", 0)
        act = m.get("act", "inform")
        status = "USED"
        reason = ""

        # Check if rejected
        for rej in rej_texts:
            if f"msg#{i}" in rej:
                status = "REJECTED"
                reason = rej
                break

        if status != "REJECTED":
            if act == "noise":
                status = "NOISE"
                reason = m.get("why", "no plan impact")
            elif act == "request":
                status = "REQUEST"
                reason = "Not approved (shown as optional)"

        msg_entries.append({
            "n": i,
            "text": m.get("raw", m.get("text", f"Message #{i}")),
            "date": m.get("d"),
            "act": act,
            "status": status,
            "reason": reason
        })

    # Prepare complete payload
    data_payload = {
        "run": trace.run_no,
        "mode": trace.mode,
        "run_totals": trace.run_totals(),
        "plan": plan,
        "checks": checks,
        "unresolved": unresolved,
        "messages": msg_entries,
        "trace": {
            "calls": trace.calls,
            "events": trace.events
        }
    }

    # 1. Write out/plan.json
    with open(PLAN_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data_payload, f, indent=2, ensure_ascii=False)

    # 2. Inline template assets for self-contained report.html
    current_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(current_dir, "assets")

    html_template_path = os.path.join(assets_dir, "report.html")
    css_path = os.path.join(assets_dir, "style.css")
    js_path = os.path.join(assets_dir, "app.js")

    with open(html_template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    with open(css_path, "r", encoding="utf-8") as f:
        css_content = f.read()

    with open(js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Safely replace placeholders
    rendered = html_content.replace("/* {{STYLE}} */", css_content)
    rendered = rendered.replace("/* {{APP_JS}} */", js_content)
    rendered = rendered.replace("{{DATA}}", json.dumps(data_payload, ensure_ascii=False))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    return out_path
