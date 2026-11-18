"""
Unit tests for Phase 4: FactStore and Area Planners.
Tests math formulas, round-robin judging, venue filtering, superseding logic,
and date comparisons using arbitrary and invented values.
"""

import unittest
from planner.facts import FactStore, is_newer_date, jaccard_similarity
from planner.areas import people, venue, judging, food, schedule, budget

class TestFactStore(unittest.TestCase):
    def test_date_comparison(self):
        # 11-12 is newer than 10-20
        self.assertTrue(is_newer_date("11-12", "10-20"))
        # 10-20 is older than 11-12
        self.assertFalse(is_newer_date("10-20", "11-12"))
        # Year wrap test: 01-05 should beat 11-20 when spread > 6 months
        self.assertTrue(is_newer_date("01-05", "11-20"))

    def test_jaccard_similarity(self):
        # "Standard lunch box" vs "standard box lunch"
        sim = jaccard_similarity("Standard lunch box", "Lunch box standard")
        self.assertGreaterEqual(sim, 0.6)

    def test_supersede_newer_date_wins(self):
        store = FactStore()
        # Message 1 dated Nov 10 says item A is 100
        msg1 = {
            "i": 1,
            "d": "11-10",
            "act": "inform",
            "f": [{"k": "param", "key": "students", "v": 100}]
        }
        store.add_message(msg1)
        self.assertEqual(store.params["students"]["v"], 100)

        # Message 2 dated Nov 12 says item A is 120 (newer -> replaces)
        msg2 = {
            "i": 2,
            "d": "11-12",
            "act": "inform",
            "f": [{"k": "param", "key": "students", "v": 120}]
        }
        store.add_message(msg2)
        self.assertEqual(store.params["students"]["v"], 120)

        # Message 3 dated Nov 05 says item A is 80 (older -> does NOT replace)
        msg3 = {
            "i": 3,
            "d": "11-05",
            "act": "inform",
            "f": [{"k": "param", "key": "students", "v": 80}]
        }
        store.add_message(msg3)
        self.assertEqual(store.params["students"]["v"], 120)

class TestAreaPlanners(unittest.TestCase):
    def setUp(self):
        self.store = FactStore()
        # Setup basic event parameters with arbitrary test values
        self.store.params = {
            "students": {"v": 60, "msg": 1, "date": "11-01"},
            "team_size": {"v": 3, "msg": 1, "date": "11-01"},
            "staff": {"v": 4, "msg": 1, "date": "11-01"},
            "max_teams_per_judge": {"v": 3, "msg": 1, "date": "11-01"},
            "judges_confirmed": {"v": 10, "msg": 2, "date": "11-01"},
            "honorarium": {"v": 2000, "msg": 2, "date": "11-01"},
            "min_per_team": {"v": 15, "msg": 2, "date": "11-01"},
            "budget_total": {"v": 300000, "msg": 1, "date": "11-01"},
            "duration_min": {"v": 240, "msg": 1, "date": "11-01"}
        }

    def test_people_planner(self):
        # 60 students / 3 = 20 teams. Max 3 teams per judge -> ceil(20/3) = 7 judges needed.
        # Headcount = 60 + 4 staff + 7 judges = 71.
        p = people.plan_people(self.store)
        self.assertEqual(p["teams"], 20)
        self.assertEqual(p["judges"], 7)
        self.assertEqual(p["total"], 71)

    def test_judging_planner(self):
        # 20 teams, 7 judges needed
        j = judging.plan_judging(self.store, teams=20, judges_needed=7)
        self.assertEqual(j["needed"], 7)
        self.assertEqual(j["confirmed"], 10)
        self.assertEqual(j["reserves"], 3)  # 10 - 7 = 3 reserves
        self.assertEqual(j["rounds"], 3)    # ceil(20/7) = 3 rounds
        self.assertEqual(j["cost"], 7 * 2000) # 14000
        self.assertEqual(j["minutes"], 3 * 15) # 45 minutes
        # Verify all 20 teams assigned in grid
        assigned_teams = [t for sub in j["grid"] for t in sub]
        self.assertEqual(sorted(assigned_teams), list(range(1, 21)))

    def test_venue_planner_lowest_cost_and_rules(self):
        # Add two halls: one smaller than headcount, one fitting, one fitting with higher price
        self.store.options[("venue", "Hall Small")] = {
            "name": "Hall Small", "cap": 50, "v": 20000, "feats": [], "msg": 3, "date": "11-01"
        }
        self.store.options[("venue", "Hall Big Cheap")] = {
            "name": "Hall Big Cheap", "cap": 80, "v": 50000, "feats": ["ac"], "msg": 3, "date": "11-01"
        }
        self.store.options[("venue", "Hall Big Costly")] = {
            "name": "Hall Big Costly", "cap": 100, "v": 70000, "feats": ["ac"], "msg": 3, "date": "11-01"
        }

        v = venue.plan_venue(self.store, headcount=71)
        self.assertTrue(v["ok"])
        self.assertEqual(v["name"], "Hall Big Cheap")
        self.assertEqual(v["cost"], 50000)
        
        # Verify rejected list includes Hall Small due to capacity
        rej_small = [r for r in v["rejected"] if r["name"] == "Hall Small"]
        self.assertTrue(len(rej_small) == 1)
        self.assertIn("capacity", rej_small[0]["reason"])

    def test_food_planner(self):
        self.store.options[("food", "Standard lunch")] = {
            "name": "Standard lunch", "v": 500, "tier": "std", "msg": 4, "date": "11-01"
        }
        self.store.options[("food", "Basic lunch")] = {
            "name": "Basic lunch", "v": 300, "tier": "low", "msg": 4, "date": "11-01"
        }

        f_std = food.plan_food(self.store, headcount=71, preferred_tier="std")
        self.assertEqual(f_std["cost"], 71 * 500)
        self.assertEqual(f_std["tier"], "std")

        f_low = food.plan_food(self.store, headcount=71, preferred_tier="low")
        self.assertEqual(f_low["cost"], 71 * 300)
        self.assertEqual(f_low["tier"], "low")

    def test_budget_planner_ledger(self):
        self.store.spent["printing"] = {"v": 5000, "msg": 5, "date": "11-01"}
        self.store.asks.append({"name": "DJ", "v": 10000, "msg": 6, "date": "11-01"})

        b = budget.plan_budget(self.store, venue_cost=50000, food_cost=35500, judging_cost=14000)
        # Total = 5000 + 50000 + 35500 + 14000 = 104500
        self.assertEqual(b["total"], 104500)
        self.assertEqual(b["remaining"], 300000 - 104500)
        self.assertTrue(b["ok"])
        self.assertEqual(len(b["extras"]), 1)
        self.assertTrue(b["extras"][0]["fits"])

if __name__ == "__main__":
    unittest.main()
