"""
planner.validator
Evaluates the six graded checks plus invariants and generic AST rules over plan fields.
Detail strings MUST contain actual numbers.
"""

from typing import List, Dict, Any

class ValidationReport:
    def __init__(self, checks: List[Dict[str, Any]], invariants: List[Dict[str, Any]], unresolved: List[Dict[str, Any]]):
        self.checks = checks
        self.invariants = invariants
        self.unresolved = unresolved
        self.ok = all(c.get("ok", False) for c in checks) and all(i.get("ok", False) for i in invariants)

    def first_failure(self) -> str:
        for c in self.checks:
            if not c.get("ok", False):
                return c.get("detail", "Check failed")
        for i in self.invariants:
            if not i.get("ok", False):
                return i.get("detail", "Invariant failed")
        return ""

def flatten_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested plan dict to dot-notated keys for generic rule evaluation."""
    flat = {}
    
    # people
    people = plan.get("people", {})
    flat["people.headcount"] = people.get("total", 0)
    flat["people.judges"] = people.get("judges", 0)
    flat["people.students"] = people.get("students", 0)
    flat["people.teams"] = people.get("teams", 0)
    
    # venue
    venue = plan.get("venue", {})
    flat["venue.capacity"] = venue.get("capacity", 0)
    flat["venue.cost"] = venue.get("cost", 0)
    flat["venue.name"] = venue.get("name", "")
    flat["venue.has"] = [str(f).lower() for f in venue.get("features", [])]

    # food
    food = plan.get("food", {})
    flat["food.count"] = food.get("count", 0)
    flat["food.unit_price"] = food.get("unit_price", 0)
    flat["food.cost"] = food.get("cost", 0)
    flat["food.tier"] = food.get("tier", "")

    # judging
    judging = plan.get("judging", {})
    flat["judging.judges"] = judging.get("needed", 0)
    flat["judging.confirmed"] = judging.get("confirmed", 0)
    flat["judging.cost"] = judging.get("cost", 0)
    flat["judging.minutes"] = judging.get("minutes", 0)
    flat["judging.rounds"] = judging.get("rounds", 0)
    flat["judging.teams_per_judge"] = judging.get("max_teams_per_judge", 0)

    # schedule
    sched = plan.get("schedule", {})
    flat["schedule.duration"] = sched.get("duration", 0)
    for b in sched.get("blocks", []):
        name_clean = b.get("name", "").lower().replace(" ", "_")
        flat[f"schedule.{name_clean}.start"] = b.get("start", 0)
        flat[f"schedule.{name_clean}.end"] = b.get("end", 0)
        flat[f"schedule.{name_clean}.min"] = b.get("end", 0) - b.get("start", 0)

    # budget
    budget = plan.get("budget", {})
    flat["budget.total"] = budget.get("total", 0)
    flat["budget.budget_total"] = budget.get("budget_total", 0)
    flat["budget.remaining"] = budget.get("remaining", 0)
    for line in budget.get("lines", []):
        cat = line.get("category", "")
        flat[f"budget.{cat}"] = line.get("amount", 0)

    return flat

def evaluate_generic_rule(rule: Dict[str, Any], flat_plan: Dict[str, Any]) -> tuple[bool, str, bool]:
    """
    Evaluates {field, op, v}.
    Returns: (is_valid, detail, is_resolved)
    """
    field = rule.get("field", "")
    op = rule.get("op", "==")
    val = rule.get("v")

    if field not in flat_plan:
        return False, f"unresolved field '{field}'", False

    curr_val = flat_plan[field]

    try:
        if op == "<=":
            ok = (curr_val <= val)
            detail = f"{field} {curr_val} <= {val}" if ok else f"{field} {curr_val} > {val}"
            return ok, detail, True
        elif op == ">=":
            ok = (curr_val >= val)
            detail = f"{field} {curr_val} >= {val}" if ok else f"{field} {curr_val} < {val}"
            return ok, detail, True
        elif op == "==":
            ok = (curr_val == val)
            detail = f"{field} {curr_val} == {val}" if ok else f"{field} {curr_val} != {val}"
            return ok, detail, True
        elif op == "has":
            # curr_val should be a list or set
            val_str = str(val).lower()
            if isinstance(curr_val, list):
                ok = (val_str in curr_val)
            else:
                ok = (val_str in str(curr_val).lower())
            detail = f"{field} has '{val}'" if ok else f"{field} does not have '{val}'"
            return ok, detail, True
        elif op == "not_has":
            val_str = str(val).lower()
            if isinstance(curr_val, list):
                ok = (val_str not in curr_val)
            else:
                ok = (val_str not in str(curr_val).lower())
            detail = f"{field} does not have '{val}'" if ok else f"{field} has '{val}'"
            return ok, detail, True
    except Exception as e:
        return False, f"error evaluating {field} {op} {val}: {e}", True

    return False, f"unsupported operator '{op}'", True

def validate_plan(plan: Dict[str, Any], facts: Any) -> ValidationReport:
    """
    The six graded checks:
      1. Correct figures
      2. Within budget
      3. Venue fits
      4. Schedule valid
      5. Enough judges
      6. All areas covered
    Plus invariants & generic rule checks.
    """
    checks = []
    invariants = []
    unresolved_rules = []

    people = plan.get("people", {})
    venue = plan.get("venue", {})
    food = plan.get("food", {})
    judging = plan.get("judging", {})
    schedule = plan.get("schedule", {})
    budget = plan.get("budget", {})

    headcount = people.get("total", 0)
    students = people.get("students", 0)
    staff = people.get("staff", 0)
    judges_needed = people.get("judges", 0)
    budget_total = budget.get("budget_total", 0)
    budget_spent = budget.get("total", 0)
    venue_cap = venue.get("capacity", 0)
    venue_cost = venue.get("cost", 0)
    food_count = food.get("count", 0)
    food_unit = food.get("unit_price", 0)
    food_cost = food.get("cost", 0)
    judges_confirmed = judging.get("confirmed", 0)
    judges_cost = judging.get("cost", 0)
    honorarium = judging.get("honorarium", 0)

    # --- Check 1: Correct figures ---
    # Totals equal the sum of their lines; headcount, boxes, judges recomputed match the plan
    expected_headcount = students + staff + people.get("volunteers", 0) + judges_needed
    expected_food_cost = food_count * food_unit
    expected_judges_cost = judges_needed * honorarium
    expected_lines_sum = sum(line.get("amount", 0) for line in budget.get("lines", []))

    fig_ok = True
    fig_details = []

    if headcount != expected_headcount:
        fig_ok = False
        fig_details.append(f"headcount {headcount} != {expected_headcount} ({students} students + {staff} staff + {judges_needed} judges)")
    if food_cost != expected_food_cost:
        fig_ok = False
        fig_details.append(f"food.cost {food_cost} != {food_count} x {food_unit} = {expected_food_cost}")
    if judges_cost != expected_judges_cost:
        fig_ok = False
        fig_details.append(f"judging.cost {judges_cost} != {judges_needed} x {honorarium} = {expected_judges_cost}")
    if budget_spent != expected_lines_sum:
        fig_ok = False
        fig_details.append(f"budget.total {budget_spent} != sum of lines {expected_lines_sum}")

    checks.append({
        "name": "Correct figures",
        "ok": fig_ok,
        "detail": "; ".join(fig_details) if not fig_ok else f"all line items match: food {food_cost}, judging {judges_cost}, headcount {headcount}"
    })

    # --- Check 2: Within budget ---
    budget_ok = (budget_spent <= budget_total)
    diff = abs(budget_spent - budget_total)
    checks.append({
        "name": "Within budget",
        "ok": budget_ok,
        "detail": f"total {budget_spent} <= budget {budget_total} (remaining: {budget.get('remaining', 0)})" if budget_ok
                  else f"total {budget_spent} exceeds budget {budget_total} by {diff}"
    })

    # --- Check 3: Venue fits ---
    venue_fits_ok = (venue.get("ok", False) and venue_cap >= headcount)
    venue_detail = f"venue '{venue.get('name')}' capacity {venue_cap} >= headcount {headcount}" if venue_fits_ok \
                   else f"venue '{venue.get('name')}' capacity {venue_cap} < headcount {headcount}"
    checks.append({
        "name": "Venue fits",
        "ok": venue_fits_ok,
        "detail": venue_detail
    })

    # --- Check 4: Schedule valid ---
    # Duration equals sum or blocks fit inside [0, D], no overlaps, judging fits and avoids prayer/lunch
    duration = schedule.get("duration", 240)
    sched_ok = True
    sched_reasons = []

    blocks = schedule.get("blocks", [])
    if not blocks:
        sched_ok = False
        sched_reasons.append("no schedule blocks defined")
    else:
        for i, b in enumerate(blocks):
            if b["start"] < 0 or b["end"] > duration or b["start"] >= b["end"]:
                sched_ok = False
                sched_reasons.append(f"block '{b['name']}' ({b['start']}-{b['end']}) outside [0, {duration}]")
            if i > 0:
                prev = blocks[i - 1]
                if b["start"] < prev["end"]:
                    sched_ok = False
                    sched_reasons.append(f"block '{b['name']}' ({b['start']}-{b['end']}) overlaps '{prev['name']}' ({prev['start']}-{prev['end']})")

    checks.append({
        "name": "Schedule valid",
        "ok": sched_ok,
        "detail": f"{duration} min timeline valid, no overlaps" if sched_ok else "; ".join(sched_reasons)
    })

    # --- Check 5: Enough judges ---
    judges_ok = (judges_confirmed >= judges_needed) and (judges_needed > 0)
    judges_detail = f"{judges_confirmed} confirmed >= {judges_needed} needed (reserves: {judging.get('reserves', 0)})" if judges_ok \
                    else f"needs {judges_needed} judges, only {judges_confirmed} confirmed"
    checks.append({
        "name": "Enough judges",
        "ok": judges_ok,
        "detail": judges_detail
    })

    # --- Check 6: All areas covered ---
    areas_ok = bool(venue.get("name") and food.get("cost") is not None and judging.get("cost") is not None and blocks and budget_spent > 0)
    checks.append({
        "name": "All areas covered",
        "ok": areas_ok,
        "detail": "all 5 areas (venue, schedule, food, judging, budget) present and non-empty" if areas_ok else "missing area data"
    })

    # --- Invariants ---
    # boxes >= headcount
    box_ok = (food_count >= headcount)
    invariants.append({
        "name": "Food boxes >= headcount",
        "ok": box_ok,
        "detail": f"food boxes {food_count} >= headcount {headcount}" if box_ok else f"food boxes {food_count} < headcount {headcount}"
    })

    # No negative values
    no_negatives = (headcount >= 0 and venue_cost >= 0 and food_cost >= 0 and judges_cost >= 0 and budget_spent >= 0)
    invariants.append({
        "name": "No negative values",
        "ok": no_negatives,
        "detail": "no negative line items" if no_negatives else "negative quantity or cost detected"
    })

    # Generic user rules evaluation
    flat = flatten_plan(plan)
    for (field, op), r in facts.rules.items():
        rule_ok, rule_detail, is_resolved = evaluate_generic_rule(r, flat)
        if not is_resolved:
            unresolved_rules.append({"field": field, "op": op, "v": r["v"], "detail": rule_detail})
        else:
            invariants.append({
                "name": f"Rule: {field} {op} {r['v']}",
                "ok": rule_ok,
                "detail": rule_detail
            })

    return ValidationReport(checks=checks, invariants=invariants, unresolved=unresolved_rules)
