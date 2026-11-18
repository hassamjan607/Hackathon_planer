"""
planner.areas.budget
Budget balance sheet: committed spent items + venue + food + judging.
Lists unapproved parked asks with fits_in_remaining flags.
Formulas:
  lines = spent items + venue + food + judging (+ adj)
  total = sum(lines)
  remaining = budget_total - total
  asks listed as optional extras with fits = (ask.cost <= remaining)
Pure deterministic calculation.
"""

from typing import Dict, Any, List

def plan_budget(
    facts: Any,
    venue_cost: int,
    food_cost: int,
    judging_cost: int,
    venue_name: str = "Venue",
    food_name: str = "Catering"
) -> Dict[str, Any]:
    """Calculate event budget ledger and balance."""
    params = facts.params
    spent_dict = facts.spent
    asks_list = facts.asks
    adjs = facts.adjs

    budget_total = int(params.get("budget_total", {}).get("v", 0))

    lines: List[Dict[str, Any]] = []

    # 1. Committed spent items
    for name, item in spent_dict.items():
        amt = int(item.get("v", 0))
        lines.append({
            "name": name,
            "category": "committed",
            "amount": amt,
            "src": [item.get("msg")]
        })

    # 2. Venue
    lines.append({
        "name": f"Venue ({venue_name})",
        "category": "venue",
        "amount": venue_cost,
        "src": []
    })

    # 3. Food
    lines.append({
        "name": f"Food ({food_name})",
        "category": "food",
        "amount": food_cost,
        "src": []
    })

    # 4. Judging
    lines.append({
        "name": "Judging Honorariums",
        "category": "judging",
        "amount": judging_cost,
        "src": []
    })

    # Total and remaining
    total_spent = sum(line["amount"] for line in lines)
    
    # Check total adjustment if present
    total_adj = adjs.get("total", {})
    if total_adj:
        pct = total_adj.get("pct", 0) or 0
        amt = total_adj.get("amt", 0) or 0
        total_spent = total_spent + int(total_spent * pct / 100.0) + amt

    remaining = budget_total - total_spent

    # Parked asks (optional extras)
    extras = []
    for a in asks_list:
        ask_cost = int(a.get("v", 0))
        fits = ask_cost <= remaining
        extras.append({
            "name": a.get("name", "Extra"),
            "cost": ask_cost,
            "approved": False,
            "fits": fits,
            "msg": a.get("msg")
        })

    return {
        "budget_total": budget_total,
        "lines": lines,
        "total": total_spent,
        "remaining": remaining,
        "extras": extras,
        "ok": remaining >= 0
    }
