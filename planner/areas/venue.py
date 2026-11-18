"""
planner.areas.venue
Selects the cheapest hall that satisfies capacity >= headcount and all venue.* rules.
Tie-break: smaller capacity.
Keeps rejected halls with explicit failure reasons.
Pure deterministic calculation.
"""

from typing import Dict, Any, List

def plan_venue(facts: Any, headcount: int) -> Dict[str, Any]:
    """Select optimal venue and record rejected halls."""
    options = facts.options
    rules = facts.rules
    adjs = facts.adjs

    venue_options = [opt for (cat, _), opt in options.items() if cat == "venue"]
    
    # Check for discount or tax adjustment on venue
    venue_adj = adjs.get("venue", {})
    pct_adj = venue_adj.get("pct", 0) or 0
    amt_adj = venue_adj.get("amt", 0) or 0

    valid_candidates = []
    rejected_halls = []

    # Extract venue-specific rules
    required_features = []
    max_cost_rule = None
    for (field, op), r in rules.items():
        if field == "venue.has" and op == "has":
            required_features.append(str(r["v"]).lower())
        elif field == "venue.cost" and op == "<=":
            max_cost_rule = int(r["v"])

    for opt in venue_options:
        name = opt["name"]
        raw_cap = opt.get("cap")
        cap = int(raw_cap) if raw_cap is not None else 0
        base_cost = int(opt.get("v", 0))
        adj_cost = base_cost + int(base_cost * pct_adj / 100.0) + amt_adj
        feats = [str(f).lower() for f in opt.get("feats", [])]

        reasons = []
        if cap < headcount:
            reasons.append(f"capacity {cap} < headcount {headcount}")

        for req_f in required_features:
            if req_f not in feats:
                reasons.append(f"missing required feature '{req_f}'")

        if max_cost_rule is not None and adj_cost > max_cost_rule:
            reasons.append(f"cost {adj_cost} > max allowed {max_cost_rule}")

        if not reasons:
            valid_candidates.append({
                "name": name,
                "capacity": cap,
                "cost": adj_cost,
                "base_cost": base_cost,
                "features": opt.get("feats", []),
                "src": [opt.get("msg")]
            })
        else:
            rejected_halls.append({
                "name": name,
                "capacity": cap,
                "cost": adj_cost,
                "reason": "; ".join(reasons)
            })

    if not valid_candidates:
        return {
            "name": "None",
            "capacity": 0,
            "cost": 0,
            "features": [],
            "rejected": rejected_halls,
            "ok": False
        }

    # Sort candidates by: lowest cost first, tie-break by smaller capacity
    valid_candidates.sort(key=lambda c: (c["cost"], c["capacity"]))
    chosen = valid_candidates[0]

    # Add other valid candidates as rejected with 'cheaper fitting hall exists'
    for other in valid_candidates[1:]:
        rejected_halls.append({
            "name": other["name"],
            "capacity": other["capacity"],
            "cost": other["cost"],
            "reason": f"more expensive than {chosen['name']}"
        })

    return {
        "name": chosen["name"],
        "capacity": chosen["capacity"],
        "cost": chosen["cost"],
        "features": chosen["features"],
        "rejected": rejected_halls,
        "src": chosen["src"],
        "ok": True
    }
