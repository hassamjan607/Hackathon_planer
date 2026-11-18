"""
planner.ingest
Reads UTF-8 message files exactly as given without stripping facts or normalizing slang.
Splits by blank lines or non-empty lines, assigns sequential message numbers,
and computes SHA-1 hashes of whitespace-normalised text.
Never parses senders, dates, or amounts with regex.
"""

import hashlib
import re
from typing import List, Dict, Any

def normalize_whitespace(text: str) -> str:
    """Normalize consecutive whitespace characters to a single space, stripped."""
    return " ".join(text.split()).strip()

def compute_hash(text: str) -> str:
    """Compute SHA-1 hash of whitespace-normalised text."""
    normalized = normalize_whitespace(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

def strip_list_marker(text: str) -> str:
    """
    Strip leading list marker like '1. ', '1) ', '#3 ', or '[4] ' from the start of a message
    WITHOUT editing or modifying message content.
    """
    stripped = text.strip()
    # Match leading numbering like: '1.', '1)', '#1', '[1]', '1 -'
    cleaned = re.sub(r'^(?:\[\d+\]|#\d+|\d+[\.\)\-:])\s*', '', stripped)
    return cleaned if cleaned else stripped

def read_messages(path: str, start_index: int = 1) -> List[Dict[str, Any]]:
    """
    Read UTF-8 file exactly as given.
    Splits in order:
      (1) blocks separated by blank lines;
      (2) if that yields one block but several lines, one message per non-empty line;
      (3) strip only leading list markers for numbering, never edit the content.
    Assigns sequential n starting from start_index and sha-1 hash.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    if not raw_content.strip():
        return []

    # Step 1: Split by two or more newlines (blank lines)
    raw_blocks = re.split(r'\n\s*\n+', raw_content.strip())
    
    # Step 2: If splitting gives only 1 block but has multiple non-empty lines, split per non-empty line
    if len(raw_blocks) == 1:
        lines = [line.strip() for line in raw_blocks[0].splitlines() if line.strip()]
        if len(lines) > 1:
            raw_blocks = lines

    messages = []
    current_n = start_index

    for block in raw_blocks:
        block_cleaned = block.strip()
        if not block_cleaned:
            continue
        
        # Strip only leading list marker if present
        clean_text = strip_list_marker(block_cleaned)
        h = compute_hash(clean_text)
        
        messages.append({
            "n": current_n,
            "text": clean_text,
            "raw": block_cleaned,
            "hash": h
        })
        current_n += 1

    return messages
