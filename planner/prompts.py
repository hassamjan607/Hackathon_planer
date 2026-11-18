"""
planner.prompts
Generates the reader prompt dynamically FROM planner.schema.
Ensures prompt schema and code schema never diverge.
Contains NO pack facts, prices, names, or numbers.
"""

from typing import List, Optional
from planner import schema

def build_system_prompt() -> str:
    """
    Generate the compact reader system prompt from schema definitions.
    Follows Appendix A from Winning Implementation Guide.
    """
    param_keys_str = ",".join(sorted(schema.PARAM_KEYS))
    option_cats_str = "|".join(sorted(schema.OPTION_CATS))
    option_per_str = "|".join(sorted(schema.OPTION_PER))
    option_tiers_str = "|".join(sorted(schema.OPTION_TIERS))
    adj_targets_str = "|".join(sorted(schema.ADJ_TARGETS))
    rule_ops_str = "|".join(sorted(schema.RULE_OPERATORS))
    speech_acts_str = "|".join(sorted(schema.SPEECH_ACTS))
    plan_fields_str = ", ".join(sorted(schema.PLAN_FIELD_PATHS))

    prompt = (
        "You extract planning facts from messages about a one-day event. Reply with JSON only.\n"
        "Messages may be English or Roman Urdu. Numbers are plain integers (Rs 1,200 -> 1200; lakh=100000; hazar=1000; k=1000).\n"
        f'Output: {{"m":[{{"i":<msg no>,"d":"MM-DD"|null,"act":"{speech_acts_str}","f":[<facts>],"why":"<=8 words if noise"}}]}}\n'
        "Keep JSON compact and include ALL messages in array m. Do not add markdown or explanations.\n"
        "Fact kinds:\n"
        f' {{"k":"param","key":K,"v":n|str}} K in {param_keys_str}\n'
        f' {{"k":"option","cat":"{option_cats_str}","name":s,"v":price,"per":"{option_per_str}","cap":n?,"feats":[s]?,"tier":"{option_tiers_str}"?}}\n'
        ' {"k":"spent","name":s,"v":n} already committed from the event budget\n'
        ' {"k":"block","name":s,"min":n,"at":"HH:MM"?} mandatory schedule block\n'
        ' {"k":"set","field":F,"v":n} message states a value the plan computes (proposal)\n'
        f' {{"k":"rule","field":F,"op":"{rule_ops_str}","v":x}} constraint on a plan field\n'
        f' {{"k":"adj","target":"{adj_targets_str}","pct":n?,"amt":n?}} discount, tax or surcharge\n'
        ' {"k":"ask","name":s,"v":n} request not yet approved\n'
        f"F in {plan_fields_str}, schedule.<block>.start|end|min, budget.<area>\n"
        "No chain of thought, no markdown codeblocks, only valid JSON."
    )
    return prompt

def build_user_prompt(messages: List[dict], known_keys: Optional[List[str]] = None) -> str:
    """
    Format the incoming messages and known keys for extraction.
    Placeholder template per Appendix A.
    """
    lines = []
    if known_keys:
        clean_keys = [k for k in known_keys if k]
        if clean_keys:
            lines.append("Known names (reuse exactly if referring to existing items):")
            lines.append(", ".join(clean_keys))
            lines.append("")

    lines.append("Messages:")
    for m in messages:
        i = m.get("n", m.get("i", 1))
        txt = m.get("text", "")
        lines.append(f"#{i}: {txt}")

    return "\n".join(lines)
