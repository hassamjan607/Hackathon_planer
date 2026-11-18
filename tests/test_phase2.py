"""
Unit tests for Phase 2: Ingest, State, LLM adapter, Trace, CLI mode detection.
Uses invented message text and arbitrary strings only - NO pack facts.
"""

import os
import tempfile
import unittest

from planner import ingest, state as state_mod, llm, trace as trace_mod, cli

class TestIngest(unittest.TestCase):
    def test_read_messages_blank_lines(self):
        content = "Message Alpha\n\nMessage Beta\n\n3. Message Gamma"
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name
        
        try:
            msgs = ingest.read_messages(temp_path)
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0]["n"], 1)
            self.assertEqual(msgs[0]["text"], "Message Alpha")
            self.assertEqual(msgs[1]["n"], 2)
            self.assertEqual(msgs[1]["text"], "Message Beta")
            self.assertEqual(msgs[2]["n"], 3)
            self.assertEqual(msgs[2]["text"], "Message Gamma")
            self.assertTrue(len(msgs[0]["hash"]) == 40)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_read_messages_single_block_multiline(self):
        content = "Line one\nLine two\nLine three"
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name
        
        try:
            msgs = ingest.read_messages(temp_path)
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0]["text"], "Line one")
            self.assertEqual(msgs[1]["text"], "Line two")
            self.assertEqual(msgs[2]["text"], "Line three")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

class TestState(unittest.TestCase):
    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            s = state_mod.State(
                hashes=["hash1", "hash2"],
                messages=[{"n": 1, "text": "test"}],
                facts={"test_key": 42},
                plan={"status": "ok"}
            )
            state_mod.save(s, state_path=state_file)
            loaded = state_mod.load(state_path=state_file)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.hashes, ["hash1", "hash2"])
            self.assertEqual(loaded.facts, {"test_key": 42})
            self.assertEqual(loaded.plan, {"status": "ok"})

class TestTrace(unittest.TestCase):
    def test_trace_numbering_and_events(self):
        t = trace_mod.Trace(run_no=1, mode="FULL", deadline=120.0, start_call_no=1)
        c1 = t.record_call(
            model="fake-llm",
            area="reading",
            in_tokens=100,
            out_tokens=50,
            total_tokens=150,
            input_text="input prompt",
            output_text='{"result": true}',
            ms=1200.0
        )
        self.assertEqual(c1, 1)
        t.event("SUPERSEDE", msg_ref=2, text="item A replaced item B")
        t.event("CHECK", text="6/6 passed")

        totals = t.run_totals()
        self.assertEqual(totals["calls"], 1)
        self.assertEqual(totals["in"], 100)
        self.assertEqual(totals["out"], 50)
        self.assertEqual(totals["total"], 150)

        txt = t.format_text()
        self.assertIn("CALL #1 model=fake-llm area=reading tokens in=100 out=50 total=150", txt)
        self.assertIn("SUPERSEDE msg#2: item A replaced item B", txt)
        self.assertIn("CHECK 6/6 passed", txt)
        self.assertIn("TOTAL TOKENS run 1: calls=1 in=100 out=50 total=150", txt)

    def test_update_cap_enforced(self):
        t = trace_mod.Trace(run_no=2, mode="UPDATE", deadline=60.0, start_call_no=2)
        for i in range(5):
            t.record_call("fake-llm", "reading", 10, 10, 20, "in", "out", 100.0)
        
        with self.assertRaises(trace_mod.CallLimitExceededError):
            t.record_call("fake-llm", "reading", 10, 10, 20, "in", "out", 100.0)

class TestModeDetection(unittest.TestCase):
    def test_full_mode_on_none_state(self):
        msgs = [{"hash": "h1"}, {"hash": "h2"}]
        mode, to_proc, new_m = cli.detect_mode(msgs, None)
        self.assertEqual(mode, "FULL")
        self.assertEqual(len(to_proc), 2)

    def test_noop_mode(self):
        state = state_mod.State(hashes=["h1", "h2"])
        msgs = [{"hash": "h1"}, {"hash": "h2"}]
        mode, to_proc, new_m = cli.detect_mode(msgs, state)
        self.assertEqual(mode, "NOOP")
        self.assertEqual(len(to_proc), 0)

    def test_update_mode(self):
        state = state_mod.State(hashes=["h1", "h2"])
        msgs = [{"hash": "h1"}, {"hash": "h2"}, {"hash": "h3"}]
        mode, to_proc, new_m = cli.detect_mode(msgs, state)
        self.assertEqual(mode, "UPDATE")
        self.assertEqual(len(to_proc), 1)
        self.assertEqual(to_proc[0]["hash"], "h3")

    def test_fresh_pack_reset_mode(self):
        state = state_mod.State(hashes=["old1", "old2", "old3"])
        # New pack with >= 5 messages and 0 overlap
        msgs = [{"hash": f"new_{i}"} for i in range(6)]
        mode, to_proc, new_m = cli.detect_mode(msgs, state)
        self.assertEqual(mode, "FULL")
        self.assertEqual(len(to_proc), 6)

class TestLLMAdapter(unittest.TestCase):
    def test_fake_llm_call(self):
        llm.set_fake_responses([
            {"model": "test-mock", "text": '{"status":"ok"}', "in": 80, "out": 40, "total": 120}
        ])
        res = llm.call("reading", "system test", "user test")
        self.assertEqual(res["model"], "test-mock")
        self.assertEqual(res["text"], '{"status":"ok"}')
        self.assertEqual(res["total"], 120)

if __name__ == "__main__":
    unittest.main()
