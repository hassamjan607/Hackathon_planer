"""
planner.engine
Propose, validate, commit orchestration.
Phase A: Load foundations from messages, build baseline plan, validate/repair.
Phase B: Test proposals atomically per message on a cloned copy of facts.
If valid: COMMIT, trace ACCEPT with per-area diff.
If invalid: REJECT, name exact numbers in reason, KEEP previous plan unchanged.
"""

import copy
from typing import Dict, Any, List, Optional
from planner import reader, repair
from planner.facts import FactStore, is_newer_date
from planner.areas import people, venue, judging, food, schedule, budget
from planner.validator import validate_plan, ValidationReport
from planner.state import State

class RunResult:
    def __init__(
        self,
        plan: Dict[str, Any],
        facts: FactStore,
        parsed_messages: List[Dict[str, Any]],
        trace: Any,
        state: State,
        checks: List[Dict[str, Any]],
        unresolved: List[Dict[str, Any]]
    ):
        self.plan = plan
        self.facts = facts
        self.parsed_messages = parsed_messages
        self.trace = trace
        self.state = state
        self.checks = checks
        self.unresolved = unresolved

def build_plan_from_facts(facts: FactStore, preferred_food_tier: str = "std") -> Dict[str, Any]:
    """Pure deterministic plan assembly across all 5 areas."""
    p = people.plan_people(facts)
    headcount = p["total"]
    teams = p["teams"]
    judges_needed = p["judges"]

    v = venue.plan_venue(facts, headcount=headcount)
    f = food.plan_food(facts, headcount=headcount, preferred_tier=preferred_food_tier)
    j = judging.plan_judging(facts, teams=teams, judges_needed=judges_needed)
    s = schedule.plan_schedule(facts, judging_minutes=j["minutes"])
    b = budget.plan_budget(
        facts,
        venue_cost=v.get("cost", 0),
        food_cost=f.get("cost", 0),
        judging_cost=j.get("cost", 0),
        venue_name=v.get("name", "Venue"),
        food_name=f.get("name", "Catering")
    )

    return {
        "people": p,
        "venue": v,
        "food": f,
        "judging": j,
        "schedule": s,
        "budget": b
    }

def compute_plan_diff(old_plan: Optional[Dict[str, Any]], new_plan: Dict[str, Any]) -> List[str]:
    """Compute which domain areas changed between two plans."""
    if not old_plan:
        return ["people", "venue", "food", "judging", "schedule", "budget"]

    changed_areas = []
    for area in ["people", "venue", "food", "judging", "schedule", "budget"]:
        old_val = old_plan.get(area)
        new_val = new_plan.get(area)
        # Compare key costs or counts
        if area == "budget" and (old_val.get("total") != new_val.get("total") or old_val.get("lines") != new_val.get("lines")):
            changed_areas.append("budget")
        elif area == "food" and (old_val.get("cost") != new_val.get("cost") or old_val.get("count") != new_val.get("count")):
            changed_areas.append("food")
        elif area == "venue" and (old_val.get("name") != new_val.get("name") or old_val.get("cost") != new_val.get("cost")):
            changed_areas.append("venue")
        elif area == "judging" and (old_val.get("cost") != new_val.get("cost") or old_val.get("needed") != new_val.get("needed")):
            changed_areas.append("judging")
        elif area == "people" and old_val.get("total") != new_val.get("total"):
            changed_areas.append("people")
        elif area == "schedule" and old_val.get("blocks") != new_val.get("blocks"):
            changed_areas.append("schedule")

    return changed_areas or ["budget"]

def apply_message_sets(facts: FactStore, msg: Dict[str, Any], plan: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    """
    Check if message has 'set' facts (e.g. food.count = 100).
    A 'set' proposes overriding a computed field.
    Returns: (modified_plan, error_reason_if_any)
    """
    modified_plan = copy.deepcopy(plan)
    headcount = plan["people"]["total"]
    msg_id = msg.get("i", 0)

    for f in msg.get("f", []):
        if f.get("k") == "set":
            field = f.get("field", "")
            val = f.get("v")
            if field == "food.count":
                int_val = int(val)
                if int_val < headcount:
                    reason = (
                        f"REJECT msg#{msg_id}: sets food.count={int_val} but headcount={headcount} "
                        f"({plan['people']['students']} students + {plan['people']['staff']} staff + {plan['people']['judges']} judges); "
                        f"rule boxes >= headcount; plan unchanged."
                    )
                    return plan, reason
                else:
                    # Allowed set that increases or matches boxes
                    modified_plan["food"]["count"] = int_val
                    modified_plan["food"]["cost"] = int_val * modified_plan["food"]["unit_price"]
                    # Recompute budget
                    modified_plan["budget"] = budget.plan_budget(
                        facts,
                        venue_cost=modified_plan["venue"]["cost"],
                        food_cost=modified_plan["food"]["cost"],
                        judging_cost=modified_plan["judging"]["cost"],
                        venue_name=modified_plan["venue"].get("name", "Venue"),
                        food_name=modified_plan["food"].get("name", "Catering")
                    )
    return modified_plan, None

def run(
    mode: str,
    messages: List[Dict[str, Any]],
    state: Optional[State],
    trace: Any
) -> RunResult:
    """
    Main planning execution:
      1. Exactly 1 model call (reader) to parse new messages.
      2. In FULL mode: load foundations, build plan, validate/repair.
      3. In UPDATE mode (or proposal sets): test each message atomically on a copy.
    """
    known_keys = state.keys if state else None
    
    # 1 MODEL CALL: reading
    extraction = reader.read(messages, known_keys=known_keys, trace=trace)
    parsed_msgs = extraction.get("m", [])
    unresolved_items = extraction.get("unresolved", [])

    # Initialize FactStore from state or empty
    if state and state.facts:
        facts = FactStore.from_dict(state.facts)
    else:
        facts = FactStore()

    current_plan = state.plan if (state and state.plan) else None

    # Sort parsed messages in chronological order (dates have no year)
    # Newest date wins, ties go to file position
    sorted_msgs = sorted(parsed_msgs, key=lambda m: (m.get("i", 0)))

    if mode == "FULL":
        # Phase A: Add foundations from all messages
        for msg in sorted_msgs:
            facts.add_message(msg, trace=trace)

        # Build plan
        plan = build_plan_from_facts(facts)
        report = validate_plan(plan, facts)

        # Attempt repair if invalid
        if not report.ok:
            repaired_plan, rep_report = repair.attempt_repair(facts, trace=trace)
            if repaired_plan and rep_report and rep_report.ok:
                plan = repaired_plan
                report = rep_report

        # Check for set proposals in full run
        for msg in sorted_msgs:
            plan, reject_reason = apply_message_sets(facts, msg, plan)
            if reject_reason:
                trace.event("REJECT", text=reject_reason)

        passed_checks_cnt = sum(1 for c in report.checks if c.get("ok", False))
        trace.event("CHECK", text=f"{passed_checks_cnt}/6 passed")
        current_plan = plan

    elif mode == "UPDATE":
        # Phase B: Test proposals atomically per message on a COPY of facts
        for msg in sorted_msgs:
            msg_id = msg.get("i", 0)
            cand_facts = facts.with_message(msg, trace=None) # Don't trace until accepted
            cand_plan = build_plan_from_facts(cand_facts)
            
            # Check proposal sets (e.g. food.count=100)
            cand_plan, reject_reason = apply_message_sets(cand_facts, msg, cand_plan)
            
            if reject_reason:
                trace.event("REJECT", text=reject_reason)
                continue

            report = validate_plan(cand_plan, cand_facts)
            if not report.ok:
                rep_plan, rep_report = repair.attempt_repair(cand_facts, trace=trace)
                if rep_plan and rep_report and rep_report.ok:
                    cand_plan = rep_plan
                    report = rep_report

            if report.ok:
                # ACCEPT: Commit facts and plan
                diff_areas = compute_plan_diff(current_plan, cand_plan)
                facts = cand_facts
                facts.add_message(msg, trace=trace) # Now trace domain events
                current_plan = cand_plan
                
                # Format accept text with specific details
                diff_str = ", ".join(diff_areas)
                trace.event("ACCEPT", msg_ref=msg_id, text=f"affected areas: {diff_str}")
            else:
                failure_reason = report.first_failure()
                trace.event("REJECT", msg_ref=msg_id, text=f"{failure_reason}; plan unchanged")

    # Final report on committed plan
    final_report = validate_plan(current_plan, facts)
    
    # Update state
    all_hashes = list(state.hashes) if state else []
    for m in messages:
        if m.get("hash") and m["hash"] not in all_hashes:
            all_hashes.append(m["hash"])

    new_state = State(
        hashes=all_hashes,
        messages=state.messages + messages if state else messages,
        facts=facts.to_dict(),
        plan=current_plan,
        runs=state.runs if state else [],
        keys=facts.get_known_keys()
    )

    return RunResult(
        plan=current_plan,
        facts=facts,
        parsed_messages=parsed_msgs,
        trace=trace,
        state=new_state,
        checks=final_report.checks,
        unresolved=unresolved_items
    )
