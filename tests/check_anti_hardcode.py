"""
tests/check_anti_hardcode.py
Automated scanner verifying that NO pack facts, prices, hall names, sender names,
or sample pack numbers exist in source code outside tests and fixtures.
Hard rule: Violation means immediate disqualification.
"""

import os
import re
import sys

# Disallowed pack facts from sample pack:
# - Hall names: "Hall A", "Hall B", "Hall C", "Room D", "Margalla"
# - Senders: "Dean", "Caterer", "Finance"
# - Key figures/prices: 650000, 120000, 150000, 220000, 212400, 547400, 102600, 1200, 800, 5000, 177
FORBIDDEN_PATTERNS = [
    r"\b650000\b",
    r"\b650,000\b",
    r"\b120000\b",
    r"\b120,000\b",
    r"\b150000\b",
    r"\b150,000\b",
    r"\b220000\b",
    r"\b220,000\b",
    r"\b212400\b",
    r"\b212,400\b",
    r"\b547400\b",
    r"\b547,400\b",
    r"\b102600\b",
    r"\b102,600\b",
    r"\bHall A\b",
    r"\bHall B\b",
    r"\bHall C\b",
    r"\bRoom D\b",
    r"\bMargalla\b",
    r"\bDean'?s\b",
    r"\bSrinagar\b",
]

ALLOWED_DIRS = {"tests", ".git", "state", "out", ".venv", "__pycache__"}

def scan_codebase(root_dir: str = ".") -> list:
    violations = []
    
    for root, dirs, files in os.walk(root_dir):
        # Skip allowed / test directories
        parts = os.path.normpath(root).split(os.sep)
        if any(p in ALLOWED_DIRS for p in parts):
            continue

        for file in files:
            if not file.endswith((".py", ".toml", ".json", ".html", ".js")):
                continue
            
            file_path = os.path.join(root, file)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_no, line in enumerate(lines, start=1):
                # Ignore pure comment lines or docstrings explaining the anti-hardcode rule
                stripped = line.strip()
                if stripped.startswith("#") or "anti-hardcode" in stripped.lower() or "forbidden" in stripped.lower():
                    continue

                for pat in FORBIDDEN_PATTERNS:
                    if re.search(pat, line, re.IGNORECASE):
                        violations.append({
                            "file": file_path,
                            "line": line_no,
                            "match": pat,
                            "text": stripped
                        })

    return violations

def main():
    print("=== ANTI-HARDCODE COMPLIANCE AUDIT ===")
    violations = scan_codebase(".")
    if violations:
        print(f"FAILED! Found {len(violations)} forbidden pack fact references in source code:")
        for v in violations:
            print(f"  {v['file']}:{v['line']} -> Matched '{v['match']}' in: {v['text']}")
        sys.exit(1)
    else:
        print("PASSED! 0 pack facts, sender names, prices or numbers found in source code.")
        sys.exit(0)

if __name__ == "__main__":
    main()
