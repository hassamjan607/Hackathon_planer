"""
Unit tests for Phase 3: Prompt generation, Reader, JSON repair fallback, Schema checking.
"""

import unittest
from planner import prompts, reader, schema, llm, trace as trace_mod

class TestPrompts(unittest.TestCase):
    def test_system_prompt_contains_all_schema_keys(self):
        sys_prompt = prompts.build_system_prompt()
        self.assertIn("students", sys_prompt)
        self.assertIn("budget_total", sys_prompt)
        self.assertIn("venue", sys_prompt)
        self.assertIn("food", sys_prompt)
        self.assertIn("block", sys_prompt)
        self.assertIn("inform", sys_prompt)
        self.assertIn("noise", sys_prompt)

    def test_user_prompt_includes_known_keys(self):
        msgs = [{"n": 1, "text": "Hello world"}]
        u_prompt = prompts.build_user_prompt(msgs, known_keys=["Hall A", "Standard lunch box"])
        self.assertIn("Hall A", u_prompt)
        self.assertIn("Standard lunch box", u_prompt)
        self.assertIn("#1: Hello world", u_prompt)

class TestReader(unittest.TestCase):
    def test_reader_clean_extraction(self):
        llm.set_fake_responses([{
            "model": "fake-reader",
            "text": '{"m":[{"i":1,"d":"11-01","act":"inform","f":[{"k":"param","key":"students","v":100}]}]}',
            "in": 200,
            "out": 50,
            "total": 250
        }])
        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": 1, "text": "100 students"}]
        res = reader.read(msgs, trace=t)
        self.assertEqual(len(res["m"]), 1)
        self.assertEqual(res["m"][0]["act"], "inform")
        self.assertEqual(res["m"][0]["f"][0]["v"], 100)
        self.assertEqual(len(t.calls), 1)

    def test_reader_drops_unknown_kinds_and_logs_note(self):
        llm.set_fake_responses([{
            "model": "fake-reader",
            "text": '{"m":[{"i":1,"d":"11-01","act":"inform","f":[{"k":"alien_kind","foo":"bar"},{"k":"param","key":"students","v":50}]}]}',
            "in": 150,
            "out": 40,
            "total": 190
        }])
        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": 1, "text": "50 students"}]
        res = reader.read(msgs, trace=t)
        # alien_kind should be dropped
        self.assertEqual(len(res["m"][0]["f"]), 1)
        self.assertEqual(res["m"][0]["f"][0]["k"], "param")
        # NOTE event logged in trace
        notes = [e for e in t.events if e["type"] == "NOTE"]
        self.assertTrue(any("Dropped unknown fact kind 'alien_kind'" in n["text"] for n in notes))

    def test_reader_one_repair_retry_on_bad_json(self):
        # 1st response is malformed JSON, 2nd response is repaired valid JSON
        llm.set_fake_responses([
            {"model": "fake-reader", "text": "broken json {not valid", "in": 100, "out": 10, "total": 110},
            {"model": "fake-reader", "text": '{"m":[{"i":1,"d":null,"act":"noise","why":"unclear","f":[]}]}', "in": 120, "out": 20, "total": 140}
        ])
        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0)
        msgs = [{"n": 1, "text": "unclear text"}]
        res = reader.read(msgs, trace=t)
        self.assertEqual(len(res["m"]), 1)
        self.assertEqual(res["m"][0]["act"], "noise")
        # Proves 2 numbered model calls happened (1 initial + 1 repair)
        self.assertEqual(len(t.calls), 2)
        self.assertEqual(t.calls[0]["n"], 1)
        self.assertEqual(t.calls[1]["n"], 2)

if __name__ == "__main__":
    unittest.main()
