#!/usr/bin/env python
"""
MatSelect 后端底座验证脚本（技术负责人用于集成前核查）。

用法（Windows PowerShell）：
    cd D:\\Documents\\MyDoc\\CODE\\MatSelect\\backend
    & "C:\\Users\\73937\\.workbuddy\\binaries\\python\\envs\\matselect\\Scripts\\python.exe" ..\\tools\\verify_backend.py

检查项：
    1. 模块可导入（app.main / app.core.* / app.db.* / app.repository.base）
    2. 数据库已建、表清单完整
    3. material_fts 存在且分词器可用（trigram 优先，unicode61 兜底）
    4. FTS 同步触发器存在
    5. FastAPI 应用可装配、/openapi.json 可访问
    6. repository/base.py 的 BaseRepository 方法签名与契约一致
结果写入 tools/_verify_backend.txt（UTF-8），并打印到 stdout。
"""
from __future__ import annotations

import inspect
import json
import os
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

REQUIRED_TABLES = {
    "category", "material", "material_fts", "material_relation", "material_revision",
    "selection_task", "task_message", "shortlist_item", "recommendation_feedback",
    "material_negative_feedback", "requirement_gap", "term_alias",
    "operation_log", "settings_kv", "import_staging", "app_meta",
}
REQUIRED_TRIGGERS = {"material_ai", "material_ad", "material_au"}
BASE_METHODS = [
    "query_all", "query_one", "scalar", "execute", "execute_many", "rowcount", "tx",
    "now_iso", "new_uid",
]

lines: list[str] = []
ok = True


def check(label: str, passed: bool, detail: str = "") -> None:
    global ok
    if not passed:
        ok = False
    lines.append(f"[{'OK ' if passed else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))


# 1. 模块导入
try:
    import app.main as main_mod  # noqa: F401
    from app.core import config, errors, logging as applogging  # noqa: F401
    from app.db import connection  # noqa: F401
    from app.repository.base import BaseRepository

    check("模块导入 app.main / core / db / repository.base", True,
          f"APP_VERSION={getattr(config, 'APP_VERSION', '?')}")
except Exception as exc:  # pragma: no cover
    check("模块导入", False, f"{type(exc).__name__}: {exc}")
    BaseRepository = None  # type: ignore
    config = None  # type: ignore

# 2. 数据库与表
db_path = None
if config is not None:
    db_path = Path(str(config.DB_PATH))
check("数据库文件存在", bool(db_path and db_path.exists()), str(db_path))

if db_path and db_path.exists():
    con = sqlite3.connect(str(db_path))
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    missing = sorted(REQUIRED_TABLES - tables)
    check("表清单完整（含 4 张支撑表）", not missing,
          f"缺失 {missing}" if missing else f"{len(tables)} 张表")

    triggers = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    miss_t = sorted(REQUIRED_TRIGGERS - triggers)
    check("FTS5 同步触发器（material_ai/ad/au）", not miss_t,
          f"缺失 {miss_t}" if miss_t else "齐全")

    # 3. FTS5 分词器
    ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='material_fts'").fetchone()
    tok = "unknown"
    if ddl and ddl[0]:
        low = ddl[0].lower()
        tok = "trigram" if "trigram" in low else ("unicode61" if "unicode61" in low else "default/unknown")
    check("material_fts 分词器可用", tok in ("trigram", "unicode61"), f"tokenizer={tok}")
    con.close()

# 4. FastAPI 装配 + /openapi.json
try:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/openapi.json")
    paths = sorted(r.json().get("paths", {}).keys()) if r.status_code == 200 else []
    check("应用装配 / openapi.json", r.status_code == 200,
          f"HTTP {r.status_code}, 已注册路由 {len(paths)} 条")
    if paths:
        lines.append("       已注册路径: " + ", ".join(paths))
    # 404 错误体形状（若 materials 路由已就绪）
    r404 = client.get("/api/materials/no-such-uid-000")
    body_ok = False
    try:
        j = r404.json()
        body_ok = "error" in j and "code" in j["error"]
    except Exception:
        pass
    check("统一错误体 {error:{code,message}}", r404.status_code in (404, 500) and body_ok,
          f"HTTP {r404.status_code}")
except Exception as exc:
    check("应用装配 / TestClient", False, f"{type(exc).__name__}: {exc}")

# 5. BaseRepository 签名
if BaseRepository is not None:
    found = [m for m in BASE_METHODS if hasattr(BaseRepository, m)]
    missing_m = sorted(set(BASE_METHODS) - set(found))
    check("BaseRepository 契约方法齐备", not missing_m,
          f"缺失 {missing_m}" if missing_m else f"{len(found)} 个方法")

lines.insert(0, "===== MatSelect 后端底座验证 =====")
lines.append("")
lines.append("RESULT: " + ("PASS" if ok else "FAIL"))

report = ROOT / "tools" / "_verify_backend.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass
print("\n".join(lines))
raise SystemExit(0 if ok else 1)
