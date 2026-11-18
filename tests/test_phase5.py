"""
Unit tests for Phase 5: Validator, Repair, Engine (Propose-Validate-Commit).
Tests rejection of invalid messages with explicit numbers and acceptance of valid changes.
"""

import json
import unittest
from planner import engine, state as state_mod, trace as trace_mod, llm
from planner.facts import FactStore
from planner.validator import validate_plan

class TestPhase5Engine(unittest.TestCase):
    def setUp(self):
        # Sample pack extraction mock
        with open("tests/fixtures/sample_pack_expected.json", "r", encoding="utf-8") as f:
            self.sample_expected = json.load(f)

    def test_full_run_sample_pack_numbers(self):
        """Verify initial full run computes 177 headcount, 547,400 spent, 102,600 remaining."""
        llm.set_fake_responses([{
            "model": "fake-model",
            "text": json.dumps(self.sample_expected),
            "in": 812,
            "out": 341,
            "total": 1153
        }])

        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": i + 1, "text": f"msg {i+1}", "hash": f"h_{i+1}"} for i in range(8)]
        res = engine.run(mode="FULL", messages=msgs, state=None, trace=t)

        plan = res.plan
        # 1. Headcount = 150 + 10 + 17 = 177
        self.assertEqual(plan["people"]["total"], 177)
        self.assertEqual(plan["people"]["judges"], 17)
        # 2. Venue Hall A = 120,000
        self.assertEqual(plan["venue"]["cost"], 120000)
        self.assertEqual(plan["venue"]["name"], "Hall A")
        # 3. Food 177 x 1,200 = 212,400
        self.assertEqual(plan["food"]["cost"], 212400)
        # 4. Judging 17 x 5,000 = 85,000
        self.assertEqual(plan["judging"]["cost"], 85000)
        # 5. Budget total: 130k committed + 120k + 212.4k + 85k = 547,400
        self.assertEqual(plan["budget"]["total"], 547400)
        self.assertEqual(plan["budget"]["remaining"], 102600)

        # Verify all 6 checks passed
        all_passed = all(c["ok"] for c in res.checks)
        self.assertTrue(all_passed)
        # Exactly 1 model call was made
        self.assertEqual(len(t.calls), 1)

    def test_update_valid_change_accepted(self):
        """Finance change: printing 10k -> 15k accepted with 1 call, affecting only budget."""
        # Baseline run
        llm.set_fake_responses([{
            "model": "fake-model",
            "text": json.dumps(self.sample_expected),
            "in": 812,
            "out": 341,
            "total": 1153
        }])
        t1 = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": i + 1, "text": f"msg {i+1}", "hash": f"h_{i+1}"} for i in range(8)]
        res1 = engine.run(mode="FULL", messages=msgs, state=None, trace=t1)

        # Update run with finance message
        finance_parsed = {
            "m": [{
                "i": 9,
                "d": "11-15",
                "act": "inform",
                "f": [{"k": "spent", "name": "printing", "v": 15000}]
            }]
        }
        llm.set_fake_responses([{
            "model": "fake-model",
            "text": json.dumps(finance_parsed),
            "in": 210,
            "out": 40,
            "total": 250
        }])

        t2 = trace_mod.Trace(run_no=2, mode="UPDATE", deadline=60.0, start_call_no=2)
        new_msg = [{"n": 9, "text": "printing bill 15k", "hash": "h_9"}]
        res2 = engine.run(mode="UPDATE", messages=new_msg, state=res1.state, trace=t2)

        # Printing changed by +5,000 -> Total becomes 552,400; remaining becomes 97,600
        self.assertEqual(res2.plan["budget"]["total"], 552400)
        self.assertEqual(res2.plan["budget"]["remaining"], 97600)
        # Trace has ACCEPT event
        accepts = [e for e in t2.events if e["type"] == "ACCEPT"]
        self.assertEqual(len(accepts), 1)
        self.assertIn("budget", accepts[0]["text"])

    def test_update_wrong_message_rejected_with_numbers(self):
        """Caterer reduces to 100 boxes -> REJECTED because 100 < 177, plan kept unchanged."""
        # Baseline run
        llm.set_fake_responses([{
            "model": "fake-model",
            "text": json.dumps(self.sample_expected),
            "in": 812,
            "out": 341,
            "total": 1153
        }])
        t1 = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": i + 1, "text": f"msg {i+1}", "hash": f"h_{i+1}"} for i in range(8)]
        res1 = engine.run(mode="FULL", messages=msgs, state=None, trace=t1)

        # Wrong message parsed
        caterer_parsed = {
            "m": [{
                "i": 10,
                "d": "11-15",
                "act": "inform",
                "f": [{"k": "set", "field": "food.count", "v": 100}]
            }]
        }
        llm.set_fake_responses([{
            "model": "fake-model",
            "text": json.dumps(caterer_parsed),
            "in": 210,
            "out": 40,
            "total": 250
        }])

        t2 = trace_mod.Trace(run_no=2, mode="UPDATE", deadline=60.0, start_call_no=2)
        wrong_msg = [{"n": 10, "text": "rounded down to 100 boxes", "hash": "h_10"}]
        res2 = engine.run(mode="UPDATE", messages=wrong_msg, state=res1.state, trace=t2)

        # Plan MUST be unchanged (food count still 177, budget still 547,400)
        self.assertEqual(res2.plan["food"]["count"], 177)
        self.assertEqual(res2.plan["budget"]["total"], 547400)

        # Trace has REJECT event containing explicit numbers
        rejects = [e for e in t2.events if e["type"] == "REJECT"]
        self.assertTrue(len(rejects) >= 1)
        reason_text = rejects[0]["text"]
        self.assertIn("100", reason_text)
        self.assertIn("177", reason_text)
        self.assertIn("plan unchanged", reason_text)

if __name__ == "__main__":
    unittest.main()
