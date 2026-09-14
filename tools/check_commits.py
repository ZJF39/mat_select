#!/usr/bin/env python
"""Verify that git commit subjects are valid UTF-8 (ASCII-only source; the
mojibake markers below are written as unicode escapes on purpose)."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKERS = tuple(chr(c) for c in (0x9342, 0x9423, 0x9528, 0x94A3, 0x94DF, 0x93BB, 0x94E8, 0x6D93, 0x7EDB, 0x94CB))

def main() -> int:
    n = sys.argv[1] if len(sys.argv) > 1 else "20"
    p = subprocess.run(["git", "log", "-" + n, "--pretty=%h\x1f%s"], cwd=ROOT, capture_output=True)
    if p.returncode != 0:
        return 2
    raw = p.stdout
    try:
        text = raw.decode("utf-8"); enc = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("gbk", "replace"); enc = "gbk"
    lines = ["decode=" + enc]
    bad = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        sha, _, subj = line.partition("\x1f")
        hit = [m for m in MARKERS if m in subj]
        if hit:
            bad += 1
            lines.append("[MOJIBAKE] " + sha)
        else:
            lines.append("[OK] " + sha + " " + subj)
    if enc != "utf-8":
        rc = 1; lines.append("RESULT: commit objects are not UTF-8")
    elif bad:
        rc = 1; lines.append("RESULT: %d commit(s) look mojibake" % bad)
    else:
        rc = 0; lines.append("RESULT: all checked commits are valid UTF-8")
    (ROOT / "tools" / "_commit_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rc

if __name__ == "__main__":
    raise SystemExit(main())