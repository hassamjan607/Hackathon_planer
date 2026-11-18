"""
Unit tests for Phase 7: Hardening, Cumulative Trace across multiple runs,
Timeouts, and Invented Packs with unseen constraint types (generator requirement,
GST food tax, and custom limits).
"""

import json
import os
import shutil
import unittest
from planner import cli, engine, state as state_mod, trace as trace_mod, llm, ingest

class TestPhase7Hardening(unittest.TestCase):
    def setUp(self):
        # Ensure fresh state/ and out/ directories for testing
        for d in ["state", "out"]:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except Exception:
                    pass

    def tearDown(self):
        for d in ["state", "out"]:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except Exception:
                    pass

    def test_cumulative_trace_across_multiple_runs(self):
        """Verify out/trace.txt records all runs cumulatively across session with correct total tokens."""
        # Run 1: FULL run with sample pack
        with open("tests/fixtures/sample_pack_expected.json", "r", encoding="utf-8") as f:
            sample_exp = json.load(f)

        llm.set_fake_responses([
            {"model": "test-small-model", "text": json.dumps(sample_exp), "in": 812, "out": 341, "total": 1153}
        ])

        ret1 = cli.run_cli(["tests/fixtures/sample_pack.txt"])
        self.assertEqual(ret1, 0)
        self.assertTrue(os.path.exists(trace_mod.TRACE_TXT_FILE))

        with open(trace_mod.TRACE_TXT_FILE, "r", encoding="utf-8") as f:
            trace_content1 = f.read()

        self.assertIn("=== RUN 1 (FULL) ===", trace_content1)
        self.assertIn("CALL #1 model=test-small-model area=reading tokens in=812 out=341 total=1153", trace_content1)
        self.assertIn("TOTAL TOKENS run 1: calls=1 in=812 out=341 total=1153", trace_content1)

        # Run 2: UPDATE with finance change (printing bill 15,000)
        finance_parsed = {
            "m": [{
                "i": 9,
                "d": "11-15",
                "act": "inform",
                "f": [{"k": "spent", "name": "printing", "v": 15000}]
            }]
        }
        llm.set_fake_responses([
            {"model": "test-small-model", "text": json.dumps(finance_parsed), "in": 210, "out": 40, "total": 250}
        ])

        ret2 = cli.run_cli(["tests/fixtures/practice_msg1.txt"])
        self.assertEqual(ret2, 0)

        with open(trace_mod.TRACE_TXT_FILE, "r", encoding="utf-8") as f:
            trace_content2 = f.read()

        # Cumulative verification: both RUN 1 and RUN 2 are present
        self.assertIn("=== RUN 1 (FULL) ===", trace_content2)
        self.assertIn("=== RUN 2 (UPDATE) ===", trace_content2)
        self.assertIn("CALL #2 model=test-small-model area=reading", trace_content2)
        self.assertIn("TOTAL TOKENS (all runs): calls=2 total=1403", trace_content2)

    def test_invented_pack_with_generator_rule(self):
        """
        Verify invented pack with unseen constraints:
          - 300 students in teams of 4 -> 75 teams
          - Max 3 teams per judge -> 25 judges needed
          - 15 staff -> Headcount = 300 + 15 + 25 = 340
          - Hall Alpha (250 cap, no generator) vs Hall Beta (400 cap, with generator)
          - Rule: venue.has generator
        Hall Beta MUST be selected because Hall Alpha is too small and lacks generator.
        """
        invented_parsed = {
            "m": [
                {
                    "i": 1,
                    "d": "11-01",
                    "act": "inform",
                    "f": [
                        {"k": "param", "key": "students", "v": 300},
                        {"k": "param", "key": "team_size", "v": 4},
                        {"k": "param", "key": "budget_total", "v": 950000},
                        {"k": "param", "key": "staff", "v": 15},
                        {"k": "block", "name": "prayer break", "min": 15}
                    ]
                },
                {
                    "i": 2,
                    "d": "11-02",
                    "act": "inform",
                    "f": [
                        {"k": "option", "cat": "venue", "name": "Hall Alpha", "v": 180000, "cap": 250, "feats": []},
                        {"k": "option", "cat": "venue", "name": "Hall Beta", "v": 260000, "cap": 400, "feats": ["generator"]}
                    ]
                },
                {
                    "i": 3,
                    "d": "11-03",
                    "act": "inform",
                    "f": [
                        {"k": "rule", "field": "venue.has", "op": "has", "v": "generator"}
                    ]
                },
                {
                    "i": 4,
                    "d": "11-04",
                    "act": "inform",
                    "f": [
                        {"k": "option", "cat": "food", "name": "Standard biryani box", "v": 1100, "tier": "std", "per": "head"}
                    ]
                },
                {
                    "i": 5,
                    "d": "11-05",
                    "act": "inform",
                    "f": [
                        {"k": "param", "key": "judges_confirmed", "v": 30},
                        {"k": "param", "key": "honorarium", "v": 4000},
                        {"k": "param", "key": "min_per_team", "v": 12},
                        {"k": "param", "key": "max_teams_per_judge", "v": 3}
                    ]
                },
                {
                    "i": 6,
                    "d": "11-06",
                    "act": "inform",
                    "f": [
                        {"k": "spent", "name": "prizes", "v": 150000},
                        {"k": "spent", "name": "badges and printing", "v": 30000}
                    ]
                }
            ]
        }

        llm.set_fake_responses([
            {"model": "test-small-model", "text": json.dumps(invented_parsed), "in": 600, "out": 300, "total": 900}
        ])

        msgs = ingest.read_messages("tests/fixtures/invented_pack.txt")
        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        res = engine.run(mode="FULL", messages=msgs, state=None, trace=t)

        plan = res.plan
        # 300 students, 75 teams, 25 judges needed -> headcount = 340
        self.assertEqual(plan["people"]["total"], 340)
        self.assertEqual(plan["people"]["judges"], 25)
        # Hall Beta selected due to generator requirement and capacity
        self.assertEqual(plan["venue"]["name"], "Hall Beta")
        self.assertEqual(plan["venue"]["cost"], 260000)
        # All 6 checks pass
        self.assertTrue(all(c["ok"] for c in res.checks))

    def test_fresh_pack_overlap_resets_stale_state(self):
        """When an entirely new pack arrives (>= 5 messages, 0 overlap), state is automatically reset."""
        # Initial pack
        state = state_mod.State(hashes=["old_1", "old_2", "old_3", "old_4", "old_5"])
        # New pack with 6 distinct messages
        new_msgs = [{"hash": f"new_pack_hash_{i}"} for i in range(6)]
        
        mode, to_proc, _ = cli.detect_mode(new_msgs, state)
        self.assertEqual(mode, "FULL")
        self.assertEqual(len(to_proc), 6)

if __name__ == "__main__":
    unittest.main()
