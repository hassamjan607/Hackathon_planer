"""
planner.repair
Downgrade strategies when plan fails budget check.
Ladder (from config/policy.toml):
  1. food std -> low (cheaper lunch tier)
  2. cheaper valid venue that still fits headcount and rules
Traces REPAIR event with exact amount saved.
"""

from typing import Tuple, Optional, Any, Dict
from planner.areas import people, venue, judging, food, schedule, budget
from planner.validator import validate_plan, ValidationReport

def attempt_repair(facts: Any, trace: Optional[Any] = None) -> Tuple[Optional[Dict[str, Any]], Optional[ValidationReport]]:
    """
    Attempt downgrade strategies to fix budget overspend.
    Returns: (repaired_plan, validation_report) or (None, None)
    """
    # Baseline calculations
    p = people.plan_people(facts)
    headcount = p["total"]
    teams = p["teams"]
    judges_needed = p["judges"]

    j = judging.plan_judging(facts, teams=teams, judges_needed=judges_needed)
    s = schedule.plan_schedule(facts, judging_minutes=j["minutes"])

    # --- Strategy 1: Food downgrade (std -> low) ---
    f_low = food.plan_food(facts, headcount=headcount, preferred_tier="low")
    v_curr = venue.plan_venue(facts, headcount=headcount)

    if f_low.get("ok"):
        b_low = budget.plan_budget(
            facts,
            venue_cost=v_curr["cost"],
            food_cost=f_low["cost"],
            judging_cost=j["cost"],
            venue_name=v_curr["name"],
            food_name=f_low["name"]
        )
        plan_cand = {
            "people": p,
            "venue": v_curr,
            "food": f_low,
            "judging": j,
            "schedule": s,
            "budget": b_low
        }
        report = validate_plan(plan_cand, facts)
        if report.ok:
            if trace:
                f_std = food.plan_food(facts, headcount=headcount, preferred_tier="std")
                savings = f_std["cost"] - f_low["cost"]
                trace.event("REPAIR", text=f"downgraded food tier to 'low' (saved Rs {savings})")
            return plan_cand, report

    # --- Strategy 2: Cheaper venue ---
    venue_options = [opt for (c, _), opt in facts.options.items() if c == "venue" and opt.get("cap", 0) >= headcount]
    venue_options.sort(key=lambda o: o.get("v", 0))

    for opt in venue_options:
        v_cand = {
            "name": opt["name"],
            "capacity": opt.get("cap", 0),
            "cost": opt.get("v", 0),
            "features": opt.get("feats", []),
            "rejected": [],
            "src": [opt.get("msg")],
            "ok": True
        }
        b_cand = budget.plan_budget(
            facts,
            venue_cost=v_cand["cost"],
            food_cost=f_low["cost"] if f_low.get("ok") else 0,
            judging_cost=j["cost"],
            venue_name=v_cand["name"],
            food_name=f_low.get("name", "food")
        )
        plan_cand = {
            "people": p,
            "venue": v_cand,
            "food": f_low,
            "judging": j,
            "schedule": s,
            "budget": b_cand
        }
        report = validate_plan(plan_cand, facts)
        if report.ok:
            if trace:
                trace.event("REPAIR", text=f"selected cheaper venue '{v_cand['name']}' (cost Rs {v_cand['cost']})")
            return plan_cand, report

    return None, None
