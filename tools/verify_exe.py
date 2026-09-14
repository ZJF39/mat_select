#!/usr/bin/env python
"""MatSelect 打包产物（exe）真机验收。

目的：证明 exe 在**干净目录**里能独立跑起来，重点验证打包最易踩的三个坑：
  1. 路由是否为 0 —— PyInstaller 冻结后 pkgutil.iter_modules 枚举不到模块，
     若兜底失效会导致接口全 404（本脚本断言 /openapi.json 的路径数 >= 10 个业务路由前缀）
  2. 数据是否落在 exe 同级 data\\ —— 若写进 _MEIPASS 临时目录，重启即丢数据
  3. 前端 SPA 与深链回退是否正常

用法：
    cd D:\\Documents\\MyDoc\\CODE\\MatSelect
    & "<venv python>" tools\\verify_exe.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "release" / "MatSelect.exe"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx  # noqa: E402

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


def free_port(start: int = 8300) -> int:
    for p in range(start, start + 30):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise SystemExit("no free port")


if not EXE.exists():
    print(f"exe 不存在：{EXE}（请先执行 PyInstaller 打包）")
    raise SystemExit(2)

sandbox = Path(tempfile.mkdtemp(prefix="matselect_exe_"))
run_dir = sandbox / "run"
run_dir.mkdir()
shutil.copy2(EXE, run_dir / "MatSelect.exe")
exe_in_run = run_dir / "MatSelect.exe"

port = free_port()
base = f"http://127.0.0.1:{port}"
log_path = sandbox / "exe.log"

lines.append("===== MatSelect exe 真机验收 =====")
lines.append(f"干净目录: {run_dir}")
lines.append(f"端口    : {port}")
lines.append("")

log_fh = open(log_path, "wb")
proc = None
try:
    proc = subprocess.Popen(
        [str(exe_in_run), "--port", str(port), "--no-browser"],
        cwd=str(run_dir), stdout=log_fh, stderr=subprocess.STDOUT,
    )

    # 单文件 exe 首启需解包，放宽到 90s
    ready = False
    for _ in range(90):
        if proc.poll() is not None:
            break
        try:
            if httpx.get(f"{base}/api/health", timeout=2.0).status_code == 200:
                ready = True
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)

    log_fh.flush()
    log_txt = log_path.read_text(encoding="utf-8", errors="replace")
    first_lines = " / ".join(
        ln.strip() for ln in log_txt.splitlines() if ln.strip() and "INFO:" not in ln
    )[:220]

    check("X1", "exe 在干净目录启动并就绪", ready,
          f"exit={proc.poll()} 输出={first_lines or '(空)'}")

    if ready:
        r = httpx.get(f"{base}/api/health", timeout=10.0)
        d = r.json() if r.status_code == 200 else {}
        check("X2", "GET /api/health（材料已播种）",
              r.status_code == 200 and d.get("materials", 0) >= 50,
              f"HTTP {r.status_code} {d}")

        # 关键：路由是否被成功挂载（打包坑）
        r = httpx.get(f"{base}/openapi.json", timeout=10.0)
        paths = list((r.json().get("paths") or {}).keys()) if r.status_code == 200 else []
        biz = [p for p in paths if p.startswith("/api/")]
        check("X3", "路由挂载完整（打包后 iter_modules 失效的兜底生效）",
              len(biz) >= 25,
              f"业务路径 {len(biz)} 条（示例 {sorted(biz)[:4]}）")

        r = httpx.get(f"{base}/api/materials", params={"q": "PP", "page_size": 5}, timeout=10.0)
        d = r.json() if r.status_code == 200 else {}
        check("X4", "检索可用（<3 字符 LIKE 兜底）",
              r.status_code == 200 and d.get("total", 0) > 0,
              f"HTTP {r.status_code} total={d.get('total')}")

        r = httpx.post(f"{base}/api/recommend/run", timeout=30.0, json={
            "constraints": {"part_type": "电气件", "process": "注塑", "temp_limit": 150,
                            "extra": ["阻燃"]}})
        d = r.json() if r.status_code == 200 else {}
        leak = [x["material"]["name"] for x in d.get("results", [])
                if (x["material"].get("service_temp_limit") or -1) < 150]
        check("X5", "推荐引擎可用（硬约束零越界）",
              r.status_code == 200 and not leak,
              f"HTTP {r.status_code} 结果={len(d.get('results', []))} 越界={leak}")

        r = httpx.get(f"{base}/", timeout=10.0)
        check("X6", "SPA 首页可访问（内嵌前端产物生效）",
              r.status_code == 200 and "MatSelect" in r.text and "/assets/" in r.text,
              f"HTTP {r.status_code}")

        r = httpx.get(f"{base}/materials", timeout=10.0)
        check("X7", "SPA 深链回退（/materials）",
              r.status_code == 200 and "MatSelect" in r.text, f"HTTP {r.status_code}")

        # 数据落盘位置：必须是 exe 同级 data\，而不是 _MEIPASS
        db = run_dir / "data" / "matselect.db"
        check("X8", "数据库落在 exe 同级 data\\（非临时解包目录）",
              db.exists() and db.stat().st_size > 0,
              f"{db} exists={db.exists()} bytes={db.stat().st_size if db.exists() else 0}")

        # 写入类接口冒烟 + 审计链路。
        # 注意：PRD F2 要求记录的是「新增材料 / 编辑材料 / 归档 / 导入 / 导出 / 回评」，
        # **建任务不在记录范围内**，因此这里用「新增材料」来验证日志链路。
        r = httpx.post(f"{base}/api/tasks", json={"title": "exe 验收任务"}, timeout=10.0)
        tid = (r.json() or {}).get("id") if r.status_code == 200 else None
        ok_msg = False
        if tid:
            r2 = httpx.post(f"{base}/api/tasks/{tid}/messages",
                            json={"text": "保险丝座 注塑 150度 阻燃"}, timeout=30.0)
            ok_msg = r2.status_code == 200
        check("X9", "写入链路可用（建任务 + 会话追问）",
              bool(tid) and ok_msg, f"task_id={tid} post_msg={ok_msg}")

        r = httpx.post(f"{base}/api/materials", timeout=10.0, json={
            "name": "exe验收用材料", "short_name": "EXE-CHK",
            "service_temp_min": -20, "service_temp_max": 120, "service_temp_limit": 120,
            "molding_process": ["注塑"], "features": ["阻燃"]})
        new_uid = (r.json() or {}).get("uid") if r.status_code == 200 else None
        r_log = httpx.get(f"{base}/api/logs", params={"limit": 10}, timeout=10.0)
        items = (r_log.json() or {}).get("items", []) if r_log.status_code == 200 else []
        actions = [i.get("action") for i in items]
        check("X10", "写入成功且审计日志已记录（PRD F2）",
              bool(new_uid) and any(a == "新增材料" for a in actions),
              f"新建 uid={'有' if new_uid else '无'} 日志动作={actions[:5]}")
finally:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:  # noqa: BLE001
            proc.kill()
    try:
        log_fh.close()
    except Exception:  # noqa: BLE001
        pass
    if proc is not None and proc.poll() is None:
        pass  # 已在上方处理
    shutil.rmtree(sandbox, ignore_errors=True)

lines += ["", f"总计: 通过 {passed} / 失败 {failed}", "RESULT: " + ("PASS" if failed == 0 else "FAIL")]
report = ROOT / "tools" / "_verify_exe.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
raise SystemExit(0 if failed == 0 else 1)
