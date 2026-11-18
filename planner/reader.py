"""
planner.reader
The ONLY module that calls the LLM (tagged area='reading').
Batched single call on FULL; incremental call with known keys on UPDATE.
Validates output against schema, drops unknown kinds with a trace NOTE,
keeps unknown keys as unresolved, and performs at most 1 traced repair attempt.
"""

import json
import re
from typing import List, Dict, Any, Optional

from planner import prompts, schema, llm

def _extract_json_blob(raw_text: str) -> Optional[dict]:
    """Attempt to parse JSON directly, or extract from markdown json block or curly braces."""
    cleaned = raw_text.strip()
    # Strip markdown code block markers if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback: find outer matching { ... }
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None

def validate_reader_output(parsed: dict, trace: Optional[Any] = None) -> Dict[str, Any]:
    """
    Validate and clean reader JSON according to schema:
      - Drops unknown fact kinds with a trace NOTE.
      - Keeps unknown keys/fields flagged as 'unresolved'.
      - Coerces types where necessary.
    """
    cleaned_messages = []
    raw_m = parsed.get("m", [])
    if not isinstance(raw_m, list):
        return {"m": [], "unresolved": []}

    all_unresolved = []

    for item in raw_m:
        if not isinstance(item, dict):
            continue

        msg_id = item.get("i", 0)
        date = item.get("d")
        act = item.get("act", "inform")
        if act not in schema.SPEECH_ACTS:
            act = "inform"
        
        why = item.get("why", "")
        facts_list = item.get("f", [])
        cleaned_facts = []

        if isinstance(facts_list, list):
            for f in facts_list:
                if not isinstance(f, dict):
                    continue
                k = f.get("k")
                if k not in schema.FACT_KINDS:
                    note = f"Dropped unknown fact kind '{k}' in msg#{msg_id}"
                    if trace:
                        trace.event("NOTE", msg_ref=msg_id, text=note)
                    continue

                # Check kind-specific keys & field paths
                if k == "param":
                    key_name = f.get("key")
                    if key_name not in schema.PARAM_KEYS:
                        unres_item = {"msg": msg_id, "kind": k, "key": key_name, "val": f.get("v")}
                        all_unresolved.append(unres_item)
                        if trace:
                            trace.event("NOTE", msg_ref=msg_id, text=f"Unresolved param key '{key_name}'")
                
                elif k in ("set", "rule"):
                    field_name = f.get("field", "")
                    if not schema.is_valid_plan_field(field_name):
                        unres_item = {"msg": msg_id, "kind": k, "field": field_name, "val": f.get("v")}
                        all_unresolved.append(unres_item)
                        if trace:
                            trace.event("NOTE", msg_ref=msg_id, text=f"Unresolved plan field '{field_name}' in {k}")

                cleaned_facts.append(f)

        cleaned_messages.append({
            "i": msg_id,
            "d": date,
            "act": act,
            "f": cleaned_facts,
            "why": why
        })

    return {"m": cleaned_messages, "unresolved": all_unresolved}

def read(
    messages: List[Dict[str, Any]],
    known_keys: Optional[List[str]] = None,
    trace: Optional[Any] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Extract facts from messages with exactly 1 model call (tagged 'reading').
    If JSON is invalid, allows at most 1 traced repair retry.
    """
    if not messages:
        return {"m": [], "unresolved": []}

    system_prompt = prompts.build_system_prompt()
    user_prompt = prompts.build_user_prompt(messages, known_keys=known_keys)

    # First attempt: Call model with tag 'reading'
    call_res = llm.call(
        area="reading",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        timeout=timeout
    )

    if trace:
        trace.record_call(
            model=call_res["model"],
            area="reading",
            in_tokens=call_res["in"],
            out_tokens=call_res["out"],
            total_tokens=call_res["total"],
            input_text=f"{system_prompt}\n\n{user_prompt}",
            output_text=call_res["text"],
            ms=call_res["ms"]
        )

    parsed_json = _extract_json_blob(call_res["text"])

    # If first attempt failed to parse as valid JSON, perform at most ONE repair retry
    if parsed_json is None or "m" not in parsed_json:
        repair_system = "You are a JSON repair tool. Output only strictly valid JSON matching the requested schema."
        repair_user = f"Fix this invalid JSON response and return ONLY valid JSON matching schema:\n{call_res['text']}"
        
        repair_res = llm.call(
            area="reading",
            system_prompt=repair_system,
            user_prompt=repair_user,
            timeout=timeout
        )
        if trace:
            trace.record_call(
                model=repair_res["model"],
                area="reading",
                in_tokens=repair_res["in"],
                out_tokens=repair_res["out"],
                total_tokens=repair_res["total"],
                input_text=f"{repair_system}\n\n{repair_user}",
                output_text=repair_res["text"],
                ms=repair_res["ms"]
            )
        
        parsed_json = _extract_json_blob(repair_res["text"])
        if parsed_json is None or "m" not in parsed_json:
            if trace:
                trace.event("NOTE", text="JSON parse failed after repair attempt; keeping empty facts.")
            return {"m": [], "unresolved": []}

    return validate_reader_output(parsed_json, trace=trace)
