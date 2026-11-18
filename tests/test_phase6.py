"""
Unit tests for Phase 6: Terminal and HTML renderers.
Verifies that report.html is self-contained with no external links,
and terminal render prints trace, checks, and tables cleanly.
"""

import json
import os
import unittest
from planner.render import terminal, html
from planner import trace as trace_mod

class TestPhase6Render(unittest.TestCase):
    def setUp(self):
        self.trace = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        self.trace.record_call(
            model="test-model",
            area="reading",
            in_tokens=500,
            out_tokens=200,
            total_tokens=700,
            input_text="system + user prompt",
            output_text='{"status":"ok"}',
            ms=1500.0
        )
        self.trace.event("CHECK", text="6/6 passed")

        # Mock result
        class MockResult:
            plan = {
                "people": {"students": 60, "staff": 4, "judges": 7, "total": 71},
                "venue": {"name": "Hall Test", "capacity": 100, "cost": 50000, "features": ["ac"], "rejected": []},
                "food": {"name": "Standard Meal", "count": 71, "unit_price": 400, "cost": 28400, "tier": "std"},
                "judging": {"needed": 7, "confirmed": 10, "honorarium": 2000, "cost": 14000, "rounds": 3, "minutes": 45, "reserves": 3},
                "schedule": {"duration": 240, "blocks": [{"name": "Opening", "start": 0, "end": 15, "kind": "fixed"}]},
                "budget": {"budget_total": 200000, "total": 92400, "remaining": 107600, "lines": [], "extras": []}
            }
            checks = [{"name": "Correct figures", "ok": True, "detail": "all match"}]
            unresolved = []
            parsed_messages = [{"i": 1, "text": "Approved hackathon", "act": "inform"}]

        self.result = MockResult()

    def test_render_html_produces_self_contained_file(self):
        out_path = html.render_html(self.result, self.trace, out_path="out/test_report.html")
        self.assertTrue(os.path.exists(out_path))
        
        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check self-contained: no external CDN links
        self.assertNotIn("http://", content)
        self.assertNotIn("https://cdn", content)
        self.assertIn("window.__PLAN_DATA__", content)
        self.assertIn("Hall Test", content)
        self.assertIn("Standard Meal", content)

        # Cleanup
        if os.path.exists(out_path):
            os.remove(out_path)

    def test_terminal_render_runs_without_exception(self):
        # Simply verify that rich render executes without throwing any error
        try:
            terminal.render_terminal(self.result, self.trace)
        except Exception as e:
            self.fail(f"render_terminal raised unexpected exception: {e}")

if __name__ == "__main__":
    unittest.main()
