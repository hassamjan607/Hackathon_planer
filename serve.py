"""
serve.py
Optional lightweight stdlib HTTP server.
Serves out/report.html and provides a live endpoint to submit a new message,
calling the exact same planner engine function as the CLI.
No external frameworks (Flask/FastAPI) needed.
"""

import http.server
import json
import os
import sys
import urllib.parse
from planner import cli, state as state_mod, ingest, engine
from planner.trace import Trace, append_cumulative_trace, TRACE_TXT_FILE
from planner.render import terminal, html

PORT = 8000
REPORT_HTML_PATH = "out/report.html"

class PlanHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path in ("/", "/index.html"):
            if not os.path.exists(REPORT_HTML_PATH):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>No plan generated yet. Run 'python run.py' first.</h1>")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(REPORT_HTML_PATH, "rb") as f:
                self.wfile.write(f.read())
            return
        
        elif parsed_url.path == "/plan.json":
            plan_file = "out/plan.json"
            if os.path.exists(plan_file):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                with open(plan_file, "rb") as f:
                    self.wfile.write(f.read())
                return

        return super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/api/add_message":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(post_body)
                raw_text = data.get("message", "").strip()
                if not raw_text:
                    self._send_json({"error": "Empty message"}, status=400)
                    return

                # Process new message through planner
                curr_state = state_mod.load()
                start_n = 1
                if curr_state and curr_state.messages:
                    start_n = max(m.get("n", 0) for m in curr_state.messages) + 1

                clean_text = ingest.strip_list_marker(raw_text)
                h = ingest.compute_hash(clean_text)
                msg_obj = [{"n": start_n, "text": clean_text, "raw": raw_text, "hash": h}]

                run_no = len(curr_state.runs) + 1 if curr_state else 1
                start_call = sum(r.get("calls", 0) for r in curr_state.runs) + 1 if curr_state else 1
                trace = Trace(run_no=run_no, mode="UPDATE", deadline=60.0, start_call_no=start_call)

                result = engine.run(mode="UPDATE", messages=msg_obj, state=curr_state, trace=trace)
                html.render_html(result, trace)

                if result.state:
                    result.state.runs.append({
                        "run_no": run_no,
                        "mode": "UPDATE",
                        "calls": len(trace.calls),
                        "tokens": trace.run_totals().get("total") or 0
                    })
                    state_mod.save(result.state)

                run_text = trace.format_text(new_desc=f"msg#{start_n}")
                append_cumulative_trace(run_text)

                self._send_json({
                    "status": "ok",
                    "run_no": run_no,
                    "calls": len(trace.calls),
                    "events": trace.events
                })
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        elif parsed_url.path == "/api/admin_update":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(post_body)
                curr_state = state_mod.load()
                facts = curr_state.facts if curr_state and curr_state.facts else {}

                # Create synthetic facts directly without model call
                msg_facts = []
                if "students" in data:
                    msg_facts.append({"k": "param", "key": "students", "v": data["students"]})
                if "staff" in data:
                    msg_facts.append({"k": "param", "key": "staff", "v": data["staff"]})
                if "budget_total" in data:
                    msg_facts.append({"k": "param", "key": "budget_total", "v": data["budget_total"]})
                if "hall" in data:
                    h = data["hall"]
                    msg_facts.append({
                        "k": "option",
                        "cat": "venue",
                        "name": h["name"],
                        "cap": h["cap"],
                        "v": h["cost"],
                        "per": "total",
                        "feats": ["ac"]
                    })

                synth_msg = {
                    "i": 999,
                    "d": "11-18",
                    "act": "inform",
                    "f": msg_facts
                }

                # Evaluate update directly
                trace = Trace(run_no=len(curr_state.runs) + 1 if curr_state else 1, mode="UPDATE", deadline=60.0)
                from planner.facts import FactStore
                from planner.engine import build_plan_from_facts
                from planner.validator import validate_plan

                store = FactStore.from_dict(curr_state.facts) if curr_state and curr_state.facts else FactStore()
                store.add_message(synth_msg, trace=trace)

                new_plan = build_plan_from_facts(store)
                report = validate_plan(new_plan, store)

                curr_state.plan = new_plan
                curr_state.facts = store.to_dict()
                state_mod.save(curr_state)

                # Re-render HTML
                result = type("AdminResult", (), {
                    "plan": new_plan,
                    "facts": store,
                    "parsed_messages": curr_state.messages,
                    "checks": report.checks,
                    "unresolved": []
                })()
                html.render_html(result, trace)

                self._send_json({"status": "ok"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        self.send_error(404, "Not Found")

    def _send_json(self, obj: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode("utf-8"))

def main():
    server = http.server.HTTPServer(("127.0.0.1", PORT), PlanHandler)
    print(f"Server started at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()

if __name__ == "__main__":
    main()
