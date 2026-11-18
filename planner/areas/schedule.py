"""
planner.areas.schedule
Timetable builder honoring fixed policy blocks, mandatory blocks (prayer break),
clock-time offsets, and non-overlapping judging rounds.
Total duration = facts.params['duration_min'] or 240
Policy blocks: opening (15m), lunch (30m), closing (15m).
Prayer break: 15m.
Judging: judging_minutes.
Remaining time allocated to build sessions.
Pure deterministic calculation.
"""

from typing import Dict, Any, List

def plan_schedule(
    facts: Any,
    judging_minutes: int,
    opening_min: int = 15,
    lunch_min: int = 30,
    closing_min: int = 15
) -> Dict[str, Any]:
    """Generate conflict-free timetable."""
    params = facts.params
    blocks_store = facts.blocks

    total_duration = int(params.get("duration_min", {}).get("v", 240) or 240)

    # Mandatory blocks from facts (e.g. prayer break)
    prayer_min = 15
    for name, b in blocks_store.items():
        if "prayer" in name.lower():
            prayer_min = int(b.get("min", 15))

    # Fixed blocks:
    # 0 - opening_min: Opening
    # Build Session 1
    # Prayer break (typically at 75-90 min mark or mid-event)
    # Lunch break (typically 90-120 min)
    # Build Session 2
    # Judging (e.g. 180 - 180+judging_minutes)
    # Closing / Results: (total_duration - closing_min) to total_duration

    blocks = []
    
    # 1. Opening
    blocks.append({
        "name": "Opening & Setup",
        "start": 0,
        "end": opening_min,
        "kind": "fixed"
    })

    # Fixed landmark milestones:
    # Prayer Break: placed at 75 to (75 + prayer_min)
    prayer_start = 75
    prayer_end = prayer_start + prayer_min

    # Lunch Break: placed after prayer
    lunch_start = prayer_end
    lunch_end = lunch_start + lunch_min

    # Build 1: between Opening and Prayer
    if prayer_start > opening_min:
        blocks.append({
            "name": "Hacking Session 1",
            "start": opening_min,
            "end": prayer_start,
            "kind": "build"
        })

    # Prayer Break Block
    blocks.append({
        "name": "Prayer Break",
        "start": prayer_start,
        "end": prayer_end,
        "kind": "break"
    })

    # Lunch Break Block
    blocks.append({
        "name": "Lunch Break",
        "start": lunch_start,
        "end": lunch_end,
        "kind": "food"
    })

    # Closing session: at the end of the duration
    closing_start = total_duration - closing_min
    closing_end = total_duration

    # Judging block: placed right before closing
    judging_start = closing_start - judging_minutes
    judging_end = closing_start

    # Build 2: between Lunch and Judging
    if judging_start > lunch_end:
        blocks.append({
            "name": "Hacking Session 2",
            "start": lunch_end,
            "end": judging_start,
            "kind": "build"
        })

    # Judging Block
    blocks.append({
        "name": "Judging Rounds",
        "start": judging_start,
        "end": judging_end,
        "kind": "judging"
    })

    # Closing Block
    blocks.append({
        "name": "Closing & Results",
        "start": closing_start,
        "end": closing_end,
        "kind": "fixed"
    })

    # Sort blocks chronologically
    blocks.sort(key=lambda b: b["start"])

    return {
        "duration": total_duration,
        "blocks": blocks,
        "judging_window": {"start": judging_start, "end": judging_end},
        "prayer_window": {"start": prayer_start, "end": prayer_end},
        "lunch_window": {"start": lunch_start, "end": lunch_end}
    }
