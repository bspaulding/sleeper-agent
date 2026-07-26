#!/usr/bin/env python3
"""Fails the build if `cli/src` or `cli/tests` use banned dynamic-magic patterns.

Backstops PROJECT_PLAN.md §10.1/§10.2's "no dynamic magic" rule mechanically
for the literal, greppable cases. Doesn't replace `code-review.md` for
subtler violations (e.g. a class hierarchy that technically avoids these
tokens but still isn't functional style).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED_PATTERNS = [
    re.compile(r"\bunittest\.mock\b"),
    re.compile(r"\bmonkeypatch\b"),
    re.compile(r"\bsetattr\("),
    re.compile(r"\bexec\("),
    re.compile(r"\beval\("),
]

# getattr(x, name, default) with an explicit default is the safe, common
# case (e.g. reading an optional argparse attribute); a bare two-arg
# getattr(x, name) is the risky, dynamic-dispatch form and stays banned.
GETATTR_TWO_ARG = re.compile(r"\bgetattr\(\s*[^,]+,\s*[^,()]+\s*\)")

# Explicitly documented exceptions: (relative path, substring on the line).
ALLOWED_EXCEPTIONS: set[tuple[str, str]] = set()

SCAN_DIRS = ["src", "tests", "scripts"]


def find_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for scan_dir in SCAN_DIRS:
        directory = root / scan_dir
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.py")):
            if path == Path(__file__).resolve():
                continue
            relative = str(path.relative_to(root))
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if (relative, line.strip()) in ALLOWED_EXCEPTIONS:
                    continue
                for pattern in BANNED_PATTERNS:
                    if pattern.search(line):
                        violations.append(
                            f"{relative}:{lineno}: banned pattern {pattern.pattern!r}: {line.strip()}"
                        )
                if GETATTR_TWO_ARG.search(line) and "getattr(" in line:
                    violations.append(
                        f"{relative}:{lineno}: two-arg getattr() (no default) is banned dynamic dispatch: {line.strip()}"
                    )
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = find_violations(root)
    if violations:
        print("check_no_magic: banned dynamic-magic patterns found:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1
    print("check_no_magic: clean")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
