#!/usr/bin/env python
"""
静态排查 backend/app 下所有模块的导入可用性，一次性列出全部悬空引用。

用法：
    cd backend
    & "...\\python.exe" ..\\tools\\check_imports.py

原理：逐个 importlib.import_module('app.<...>')，捕获 ImportError 并解析
"cannot import name 'X' from 'app.Y'" 形式的消息，汇总为「缺失符号 → 依赖方」列表。
结果写入 tools/_import_check.txt（UTF-8）。
"""
from __future__ import annotations

import importlib
import re
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

APP = BACKEND / "app"
modules: list[str] = []
for p in sorted(APP.rglob("*.py")):
    rel = p.relative_to(BACKEND).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        continue
    modules.append(".".join(parts))

lines: list[str] = ["===== backend/app 导入可用性排查 =====", ""]
missing: dict[str, set[str]] = {}
ok_mods: list[str] = []
fail_mods: list[str] = []

for m in modules:
    try:
        importlib.import_module(m)
        ok_mods.append(m)
    except Exception as exc:  # noqa: BLE001
        fail_mods.append(m)
        msg = str(exc)
        mt = re.search(r"cannot import name '([^']+)' from '([^']+)'", msg)
        if mt:
            missing.setdefault(f"{mt.group(2)}::{mt.group(1)}", set()).add(m)
            lines.append(f"[FAIL] {m}")
            lines.append(f"       缺少符号 `{mt.group(1)}`（应来自 {mt.group(2)}）")
        else:
            lines.append(f"[FAIL] {m}: {type(exc).__name__}: {msg}")
            tb = traceback.format_exc().strip().splitlines()[-3:]
            for t in tb:
                lines.append("       " + t.strip())

lines.append("")
lines.append(f"模块总数={len(modules)}  可导入={len(ok_mods)}  失败={len(fail_mods)}")
if missing:
    lines.append("")
    lines.append("---- 悬空符号汇总 ----")
    for k, users in sorted(missing.items()):
        mod, name = k.split("::")
        lines.append(f"  {mod} 缺少 `{name}`  ← 被 {', '.join(sorted(users))} 引用")
lines.append("")
lines.append("RESULT: " + ("PASS" if not fail_mods else "FAIL"))

report = ROOT / "tools" / "_import_check.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass
print("\n".join(lines[:80]))
raise SystemExit(0 if not fail_mods else 1)
