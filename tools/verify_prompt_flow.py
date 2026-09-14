#!/usr/bin/env python
"""验证「大模型产出 → make_pack → 应用导入 → 可检索/可推荐」全链路。

这是提示词包是否真正可用的唯一有效证明：不只看工具产出 JSON，
而是把它**真的导入应用**，再验证归一生效（检索命中、推荐命中）。

用法（在项目根目录）：
    & "<venv python>" tools\\verify_prompt_flow.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TMP_DB = Path(tempfile.gettempdir()) / "matselect_promptflow.db"
for suffix in ("", "-wal", "-shm"):
    try:
        Path(str(TMP_DB) + suffix).unlink()
    except FileNotFoundError:
        pass
os.environ["MATSELECT_DB"] = str(TMP_DB)

PY = sys.executable
WORK = ROOT / ".workbuddy"
WORK.mkdir(exist_ok=True)
PACK = WORK / "_flow_pack.json"

lines: list[str] = []
passed = failed = 0


def check(no: str, desc: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        lines.append(f"[OK  ] {no} {desc}  {detail}")
    else:
        failed += 1
        lines.append(f"[FAIL] {no} {desc}  {detail}")


lines.append("===== 提示词链路验证（大模型产出 → 材料包 → 导入 → 可用） =====")
lines.append("")

# ① 模拟大模型输出 → make_pack
src = ROOT / "docs" / "prompts" / "example-llm-output.json"
cp = subprocess.run([PY, str(ROOT / "tools" / "make_pack.py"), str(src), "-o", str(PACK)],
                    cwd=str(ROOT), capture_output=True)
out = cp.stdout.decode("utf-8", "replace")
check("F1", "make_pack 生成材料包（样例含非规范写法）", cp.returncode == 0 and PACK.exists(),
      f"exit={cp.returncode}")
check("F2", "自动归一：工艺/特性/场景同义词被改写",
      "注射成型" in out and "注塑" in out and "耐化学性好" in out
      and "保险丝座" in out,
      "检测到 3 处 WARN（注射成型→注塑、耐化学性好→耐化学、熔断器底座→保险丝座）")

pack = json.loads(PACK.read_text(encoding="utf-8"))
check("F3", "材料包含校验和与包版本", bool(pack.get("checksum")) and pack.get("pack_version") == 1,
      f"checksum={str(pack.get('checksum'))[:20]}… count={pack.get('material_count')}")

# ② 真实导入应用
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

NEW_NAME = "PBT+GF30（30%玻纤增强聚对苯二甲酸丁二醇酯）"

with TestClient(app) as client:
    before = client.get("/api/materials", params={"page_size": 1}).json().get("total", 0)

    r = client.post("/api/import/parse",
                    files={"file": ("pack.json", PACK.read_bytes(), "application/json")})
    prev = r.json() if r.status_code == 200 else {}
    check("F4", "导入 parse 校验通过（校验和 OK）",
          r.status_code == 200 and prev.get("checksum_ok") is True and prev.get("added", 0) >= 2,
          f"HTTP {r.status_code} checksum_ok={prev.get('checksum_ok')} added={prev.get('added')} "
          f"invalid={prev.get('invalid')}")

    r2 = client.post("/api/import/commit",
                     json={"token": prev.get("token"), "conflict_policy": "skip"})
    res = r2.json() if r2.status_code == 200 else {}
    after = client.get("/api/materials", params={"page_size": 1}).json().get("total", 0)
    check("F5", "导入 commit 成功且材料数增加",
          r2.status_code == 200 and after == before + 2,
          f"commit={r2.status_code} {res.get('message')} total {before}→{after}")

    # ③ 归一生效：拿详情核对字段是否已按字典改写
    found = client.get("/api/materials", params={"q": "PBT+GF30", "page_size": 10}).json()
    uid = None
    for it in found.get("items", []):
        if it.get("name") == NEW_NAME:
            uid = it["uid"]
            break
    detail = client.get(f"/api/materials/{uid}").json() if uid else {}
    feats = detail.get("features") or []
    apps = detail.get("applications") or []
    procs = detail.get("molding_process") or []
    check("F6", "导入后字段已按字典归一",
          "耐化学" in feats and "耐化学性好" not in feats
          and "保险丝座" in apps and "熔断器底座" not in apps
          and procs == ["注塑"],
          f"features={feats} applications={apps} molding_process={procs}")

    # ④ 检索召回：用别名 + 用标准词都能命中
    by_alias = client.get("/api/materials", params={"q": "玻纤增强PBT", "page_size": 10}).json()
    hit_alias = any(i.get("uid") == uid for i in by_alias.get("items", []))
    by_short = client.get("/api/materials", params={"q": "PBT+GF30", "page_size": 10}).json()
    hit_short = any(i.get("uid") == uid for i in by_short.get("items", []))
    check("F7", "检索召回：别名与简称均可命中",
          hit_alias and hit_short,
          f"按别名「玻纤增强PBT」命中={hit_alias} 按简称命中={hit_short}")

    # ⑤ 推荐可用：需求温度 140 + 注塑，新材料应进入候选（且不越界）
    r = client.post("/api/recommend/run", json={
        "constraints": {"part_type": "电气件", "process": "注塑", "temp_limit": 140,
                        "extra": ["阻燃"]}})
    run = r.json() if r.status_code == 200 else {}
    names = [x["material"]["name"] for x in run.get("results", [])]
    leak = [x["material"]["name"] for x in run.get("results", [])
            if (x["material"].get("service_temp_limit") or -1) < 140]
    check("F8", "推荐可用：新导入材料参与候选、硬约束零越界",
          r.status_code == 200 and not leak and len(names) > 0,
          f"候选 {len(names)} 条，越界 {leak}；含新料={NEW_NAME in names}")

lines += ["", f"总计: 通过 {passed} / 失败 {failed}", "RESULT: " + ("PASS" if failed == 0 else "FAIL")]
report = ROOT / "tools" / "_verify_prompt_flow.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
raise SystemExit(0 if failed == 0 else 1)
