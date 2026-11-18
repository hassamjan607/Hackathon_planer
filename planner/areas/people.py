"""
planner.areas.people
Computes teams, judges needed, and total headcount.
Formulas:
  teams = teams or ceil(students / team_size)
  judges_needed = ceil(teams / max_teams_per_judge)
  headcount = students + staff + volunteers + judges_needed
Pure deterministic calculation. NO pack facts, NO hardcoded values.
"""

import math
from typing import Dict, Any

def plan_people(facts: Any) -> Dict[str, Any]:
    """Calculate headcount breakdown from facts."""
    params = facts.params

    students = int(params.get("students", {}).get("v", 0))
    team_size = int(params.get("team_size", {}).get("v", 1) or 1)
    
    # Check if teams count was explicitly given, otherwise compute ceil(students / team_size)
    if "teams" in params:
        teams = int(params["teams"]["v"])
    else:
        teams = math.ceil(students / team_size) if team_size > 0 else 0

    max_teams_per_judge = int(params.get("max_teams_per_judge", {}).get("v", 3) or 3)
    judges_needed = math.ceil(teams / max_teams_per_judge) if max_teams_per_judge > 0 else 0

    staff = int(params.get("staff", {}).get("v", 0))
    volunteers = int(params.get("volunteers", {}).get("v", 0))

    total_headcount = students + staff + volunteers + judges_needed

    return {
        "students": students,
        "team_size": team_size,
        "teams": teams,
        "staff": staff,
        "volunteers": volunteers,
        "judges": judges_needed,
        "total": total_headcount,
        "src": {
            "students": params.get("students", {}).get("msg"),
            "staff": params.get("staff", {}).get("msg"),
            "team_size": params.get("team_size", {}).get("msg"),
            "max_teams_per_judge": params.get("max_teams_per_judge", {}).get("msg")
        }
    }
