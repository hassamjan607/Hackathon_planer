"""
planner.areas.judging
Round-robin judging matrix, honorarium cost, and reserve pool.
Formulas:
  J = judges_needed (must be <= confirmed)
  rounds = ceil(teams / J)
  cost = J * honorarium
  team t goes to judge (t mod J), round (t div J)
  judging_minutes = rounds * min_per_team
  spare confirmed judges = confirmed - J (reserves)
Pure deterministic calculation.
"""

import math
from typing import Dict, Any, List

def plan_judging(facts: Any, teams: int, judges_needed: int) -> Dict[str, Any]:
    """Compute judging grid, honorarium cost, and reserve list."""
    params = facts.params

    confirmed = int(params.get("judges_confirmed", {}).get("v", 0))
    honorarium = int(params.get("honorarium", {}).get("v", 0))
    min_per_team = int(params.get("min_per_team", {}).get("v", 15) or 15)
    max_teams_per_judge = int(params.get("max_teams_per_judge", {}).get("v", 3) or 3)

    J = judges_needed
    rounds = math.ceil(teams / J) if J > 0 else 0
    total_cost = J * honorarium
    judging_minutes = rounds * min_per_team

    # Build round-robin grid: list of teams assigned to each judge
    # grid: [ [team1, team2, ...], [team3, team4, ...] ] per judge 0..J-1
    grid: List[List[int]] = [[] for _ in range(J)]
    for t in range(1, teams + 1):
        if J > 0:
            judge_idx = (t - 1) % J
            grid[judge_idx].append(t)

    reserves = max(0, confirmed - J)

    return {
        "needed": J,
        "confirmed": confirmed,
        "honorarium": honorarium,
        "cost": total_cost,
        "rounds": rounds,
        "minutes": judging_minutes,
        "min_per_team": min_per_team,
        "max_teams_per_judge": max_teams_per_judge,
        "grid": grid,
        "reserves": reserves,
        "src": {
            "confirmed": params.get("judges_confirmed", {}).get("msg"),
            "honorarium": params.get("honorarium", {}).get("msg"),
            "min_per_team": params.get("min_per_team", {}).get("msg")
        }
    }
