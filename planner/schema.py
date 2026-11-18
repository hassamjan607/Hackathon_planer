"""
planner.schema
Single source of truth for fact kinds, allowed keys, plan field paths, and rule operators.
Contains NO pack facts, prices, names, or numbers.
"""

from typing import Final, Set, Dict, Any, List

# Allowed fact kinds
FACT_KINDS: Final[Set[str]] = {
    "param",
    "option",
    "spent",
    "block",
    "set",
    "rule",
    "adj",
    "ask",
}

# Allowed speech acts
SPEECH_ACTS: Final[Set[str]] = {
    "inform",
    "approve",
    "request",
    "noise",
}

# Allowed parameter keys for kind="param"
PARAM_KEYS: Final[Set[str]] = {
    "students",
    "team_size",
    "teams",
    "staff",
    "volunteers",
    "duration_min",
    "budget_total",
    "start_time",
    "judges_confirmed",
    "honorarium",
    "min_per_team",
    "max_teams_per_judge",
}

# Allowed categories for kind="option"
OPTION_CATS: Final[Set[str]] = {
    "venue",
    "food",
    "other",
}

# Allowed per units for kind="option"
OPTION_PER: Final[Set[str]] = {
    "total",
    "head",
}

# Allowed tiers for kind="option"
OPTION_TIERS: Final[Set[str]] = {
    "low",
    "std",
    "high",
}

# Allowed targets for kind="adj"
ADJ_TARGETS: Final[Set[str]] = {
    "venue",
    "food",
    "total",
}

# Allowed operators for kind="rule"
RULE_OPERATORS: Final[Set[str]] = {
    "<=",
    ">=",
    "==",
    "has",
    "not_has",
}

# Allowed area tags for trace logging
AREA_TAGS: Final[Set[str]] = {
    "reading",
    "venue",
    "schedule",
    "food",
    "judging",
    "budget",
}

# Plan field paths (valid targets for 'set' and 'rule')
PLAN_FIELD_PATHS: Final[Set[str]] = {
    "people.headcount",
    "people.judges",
    "venue.capacity",
    "venue.cost",
    "venue.has",
    "food.count",
    "food.unit_price",
    "food.cost",
    "food.start",
    "judging.judges",
    "judging.cost",
    "judging.teams_per_judge",
    "judging.minutes",
    "schedule.duration",
    "budget.total",
    "budget.remaining",
}

# Dynamic prefixes for schedule and budget subfields
SCHEDULE_PREFIX: Final[str] = "schedule."
BUDGET_PREFIX: Final[str] = "budget."

def is_valid_plan_field(field: str) -> bool:
    """Check if a dot-notated field path is a recognized plan field."""
    if field in PLAN_FIELD_PATHS:
        return True
    if field.startswith(SCHEDULE_PREFIX) and (
        field.endswith(".start") or field.endswith(".end") or field.endswith(".min")
    ):
        return True
    if field.startswith(BUDGET_PREFIX):
        return True
    return False

# JSON Schema for reader validation
READER_JSON_SCHEMA: Final[Dict[str, Any]] = {
    "type": "object",
    "properties": {
        "m": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "d": {"type": ["string", "null"]},
                    "act": {"type": "string", "enum": list(SPEECH_ACTS)},
                    "f": {"type": "array"},
                    "why": {"type": "string"}
                },
                "required": ["i", "act", "f"]
            }
        }
    },
    "required": ["m"]
}
