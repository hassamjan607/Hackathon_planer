"""
planner.facts
FactStore managing state foundations and proposals.
Handles identity matching, Jaccard token-set similarity for options, temporal superseding (latest date wins),
and speech act categorization (inform/approve vs ask vs noise).
Pure deterministic code - NO LLM, NO I/O.
"""

import copy
import re
from typing import List, Dict, Any, Optional, Tuple, Set

STOP_WORDS = {"a", "an", "the", "at", "for", "in", "of", "on", "per", "box", "lunch", "wala", "ab", "hai"}

def tokenize_name(name: str) -> Set[str]:
    """Lowercase, strip non-alphanumeric, drop stop-words for token-set comparison."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", name.lower())
    tokens = {t for t in cleaned.split() if t and t not in STOP_WORDS}
    return tokens if tokens else {cleaned.strip()}

def jaccard_similarity(name1: str, name2: str) -> float:
    """Compute Jaccard token-set similarity."""
    set1 = tokenize_name(name1)
    set2 = tokenize_name(name2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

def parse_date_score(date_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """
    Parse MM-DD date string into (month, day) tuple.
    Returns None if date is missing or invalid.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    match = re.match(r"^(\d{1,2})[-/](\d{1,2})$", date_str.strip())
    if match:
        m, d = int(match.group(1)), int(match.group(2))
        return (m, d)
    return None

def is_newer_date(date_a: Optional[str], date_b: Optional[str], fallback_greater: bool = True) -> bool:
    """
    Compare date_a against date_b.
    Returns True if date_a is newer than date_b.
    Handles year-wrap: if spread exceeds 6 months, smaller month is considered in the next year.
    Ties or missing dates fall back to fallback_greater (e.g. later file order).
    """
    score_a = parse_date_score(date_a)
    score_b = parse_date_score(date_b)

    if score_a is None and score_b is None:
        return fallback_greater
    if score_a is not None and score_b is None:
        return True
    if score_a is None and score_b is not None:
        return False

    ma, da = score_a
    mb, db = score_b

    # Year wrap handling (e.g. November vs January)
    if abs(ma - mb) > 6:
        if ma < mb:
            ma += 12
        else:
            mb += 12

    if (ma, da) > (mb, db):
        return True
    elif (ma, da) < (mb, db):
        return False
    return fallback_greater


class FactStore:
    def __init__(self):
        # Keyed storage: param by key; option by (cat, name); spent by name; block by name
        self.params: Dict[str, Dict[str, Any]] = {}
        self.options: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.spent: Dict[str, Dict[str, Any]] = {}
        self.blocks: Dict[str, Dict[str, Any]] = {}
        self.rules: Dict[Tuple[str, str], Dict[str, Any]] = {}  # rule by (field, op)
        self.adjs: Dict[str, Dict[str, Any]] = {}  # adj by target
        
        # Unapproved requests and noise
        self.asks: List[Dict[str, Any]] = []
        self.noise: List[Dict[str, Any]] = []
        
        # Raw proposals and history of registered messages
        self.registered_messages: List[Dict[str, Any]] = []

    def copy(self) -> "FactStore":
        """Return a deep copy of the fact store."""
        return copy.deepcopy(self)

    def find_matching_option_key(self, cat: str, name: str) -> Optional[Tuple[str, str]]:
        """Find an existing option key in the same category using token-set Jaccard >= 0.6."""
        for (c, existing_name) in self.options.keys():
            if c == cat:
                if jaccard_similarity(existing_name, name) >= 0.6:
                    return (c, existing_name)
        return None

    def add_fact(self, fact: Dict[str, Any], msg_ref: int, date: Optional[str], trace: Optional[Any] = None) -> None:
        """
        Add a single foundation fact.
        Applies newest-date-wins rule; logs SUPERSEDE when a newer fact replaces an older one.
        """
        k = fact.get("k")
        if not k:
            return

        # 1. PARAM: identity by key
        if k == "param":
            key = fact.get("key")
            val = fact.get("v")
            if not key:
                return
            if key in self.params:
                old = self.params[key]
                if is_newer_date(date, old["date"], fallback_greater=True):
                    if trace and old["v"] != val:
                        d_old = old["date"] or "no-date"
                        d_new = date or "no-date"
                        trace.event("SUPERSEDE", msg_ref=msg_ref, text=f"param {key}: {old['v']} ({d_old}) -> {val} ({d_new})")
                    self.params[key] = {"v": val, "msg": msg_ref, "date": date}
            else:
                self.params[key] = {"v": val, "msg": msg_ref, "date": date}

        # 2. OPTION: identity by (cat, normalized name) with Jaccard >= 0.6 match
        elif k == "option":
            cat = fact.get("cat", "other")
            name = fact.get("name", "")
            match_key = self.find_matching_option_key(cat, name)
            opt_entry = {
                "name": name,
                "cat": cat,
                "v": fact.get("v", 0),
                "per": fact.get("per", "head"),
                "cap": fact.get("cap"),
                "feats": fact.get("feats", []),
                "tier": fact.get("tier"),
                "msg": msg_ref,
                "date": date
            }
            if match_key:
                old = self.options[match_key]
                if is_newer_date(date, old["date"], fallback_greater=True):
                    if trace and (old["v"] != opt_entry["v"] or old.get("tier") != opt_entry.get("tier")):
                        d_old = old["date"] or "no-date"
                        d_new = date or "no-date"
                        trace.event("SUPERSEDE", msg_ref=msg_ref, text=f"{cat} option '{old['name']}': {old['v']} ({d_old}) -> {opt_entry['v']} ({d_new})")
                    # Replace with latest name and details
                    del self.options[match_key]
                    self.options[(cat, name)] = opt_entry
            else:
                self.options[(cat, name)] = opt_entry

        # 3. SPENT: identity by name
        elif k == "spent":
            name = fact.get("name", "")
            val = fact.get("v", 0)
            if name in self.spent:
                old = self.spent[name]
                if is_newer_date(date, old["date"], fallback_greater=True):
                    if trace and old["v"] != val:
                        d_old = old["date"] or "no-date"
                        d_new = date or "no-date"
                        trace.event("SUPERSEDE", msg_ref=msg_ref, text=f"spent '{name}': {old['v']} ({d_old}) -> {val} ({d_new})")
                    self.spent[name] = {"v": val, "msg": msg_ref, "date": date}
            else:
                self.spent[name] = {"v": val, "msg": msg_ref, "date": date}

        # 4. BLOCK: identity by name
        elif k == "block":
            name = fact.get("name", "")
            if name in self.blocks:
                old = self.blocks[name]
                if is_newer_date(date, old["date"], fallback_greater=True):
                    self.blocks[name] = {"name": name, "min": fact.get("min", 0), "at": fact.get("at"), "msg": msg_ref, "date": date}
            else:
                self.blocks[name] = {"name": name, "min": fact.get("min", 0), "at": fact.get("at"), "msg": msg_ref, "date": date}

        # 5. RULE: identity by (field, op)
        elif k == "rule":
            field = fact.get("field", "")
            op = fact.get("op", "==")
            rule_entry = {"field": field, "op": op, "v": fact.get("v"), "msg": msg_ref, "date": date}
            self.rules[(field, op)] = rule_entry

        # 6. ADJ: identity by target
        elif k == "adj":
            target = fact.get("target", "total")
            adj_entry = {
                "target": target,
                "pct": fact.get("pct"),
                "amt": fact.get("amt"),
                "msg": msg_ref,
                "date": date
            }
            self.adjs[target] = adj_entry

    def add_message(self, msg: Dict[str, Any], trace: Optional[Any] = None) -> None:
        """Process a structured message object (i, d, act, f, why)."""
        msg_id = msg.get("i", 0)
        date = msg.get("d")
        act = msg.get("act", "inform")
        facts = msg.get("f", [])
        why = msg.get("why", "")

        # Record message
        self.registered_messages.append(msg)

        if act == "noise":
            self.noise.append({"msg": msg_id, "why": why, "date": date})
            if trace:
                trace.event("NOISE", msg_ref=msg_id, text=why or "unspecified reason, no plan impact")
            return

        if act == "request":
            for f in facts:
                if f.get("k") == "ask":
                    self.asks.append({"msg": msg_id, "name": f.get("name", "extra"), "v": f.get("v", 0), "date": date})
            if trace:
                for a in self.asks:
                    if a["msg"] == msg_id:
                        trace.event("ASK", msg_ref=msg_id, text=f"{a['name']} {a['v']} not approved; shown as optional")
            return

        # inform or approve: add foundations
        for f in facts:
            if f.get("k") == "ask":
                self.asks.append({"msg": msg_id, "name": f.get("name", "extra"), "v": f.get("v", 0), "date": date})
            else:
                self.add_fact(f, msg_ref=msg_id, date=date, trace=trace)

    def with_message(self, parsed_msg: Dict[str, Any], trace: Optional[Any] = None) -> "FactStore":
        """Return a cloned FactStore with the given message applied."""
        cand = self.copy()
        cand.add_message(parsed_msg, trace=trace)
        return cand

    def to_dict(self) -> Dict[str, Any]:
        """Serialize FactStore to a JSON-serializable dictionary."""
        # Convert tuple keys to string keys for options & rules
        ser_options = {f"{c}::{n}": v for (c, n), v in self.options.items()}
        ser_rules = {f"{fld}::{op}": v for (fld, op), v in self.rules.items()}
        return {
            "params": self.params,
            "options": ser_options,
            "spent": self.spent,
            "blocks": self.blocks,
            "rules": ser_rules,
            "adjs": self.adjs,
            "asks": self.asks,
            "noise": self.noise,
            "registered_messages": self.registered_messages
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactStore":
        """Deserialize FactStore from dictionary."""
        store = cls()
        store.params = data.get("params", {})
        store.spent = data.get("spent", {})
        store.blocks = data.get("blocks", {})
        store.adjs = data.get("adjs", {})
        store.asks = data.get("asks", [])
        store.noise = data.get("noise", [])
        store.registered_messages = data.get("registered_messages", [])

        # Deserialize options
        for key_str, v in data.get("options", {}).items():
            if "::" in key_str:
                c, n = key_str.split("::", 1)
                store.options[(c, n)] = v

        # Deserialize rules
        for key_str, v in data.get("rules", {}).items():
            if "::" in key_str:
                fld, op = key_str.split("::", 1)
                store.rules[(fld, op)] = v

        return store

    def get_known_keys(self) -> List[str]:
        """Return all active option names and spent item names to guide future reader extractions."""
        keys = []
        for (cat, name) in self.options.keys():
            keys.append(name)
        for name in self.spent.keys():
            keys.append(name)
        for key in self.params.keys():
            keys.append(key)
        return sorted(list(set(keys)))
