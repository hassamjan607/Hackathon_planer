"""
planner.areas.food
Headcount boxes, tier selection, rate calculations, and line cost.
Formulas:
  count = headcount
  tier = preferred_tier (std if present, else cheapest tier)
  unit_price = latest price (+ adj)
  cost = count * unit_price (+ delivery / fees)
Pure deterministic calculation.
"""

from typing import Dict, Any, List

def plan_food(facts: Any, headcount: int, preferred_tier: str = "std") -> Dict[str, Any]:
    """Calculate food catering cost and tier."""
    options = facts.options
    adjs = facts.adjs

    food_options = [opt for (cat, _), opt in options.items() if cat == "food"]
    
    # Check for discount or tax adjustment on food
    food_adj = adjs.get("food", {})
    pct_adj = food_adj.get("pct", 0) or 0
    amt_adj = food_adj.get("amt", 0) or 0

    if not food_options:
        return {
            "count": headcount,
            "tier": "none",
            "unit_price": 0,
            "cost": 0,
            "src": [],
            "ok": False
        }

    # Select candidate according to preferred tier, or fallback to cheapest
    tier_candidates = [opt for opt in food_options if opt.get("tier") == preferred_tier]
    if not tier_candidates:
        # Fallback to cheapest per-head option
        tier_candidates = sorted(food_options, key=lambda o: int(o.get("v", 0)))
    
    chosen = tier_candidates[0]
    base_unit = int(chosen.get("v", 0))
    adjusted_unit = base_unit + int(base_unit * pct_adj / 100.0) + amt_adj
    total_cost = headcount * adjusted_unit

    return {
        "count": headcount,
        "name": chosen["name"],
        "tier": chosen.get("tier", preferred_tier),
        "unit_price": adjusted_unit,
        "base_unit_price": base_unit,
        "cost": total_cost,
        "src": [chosen.get("msg")],
        "ok": True
    }
