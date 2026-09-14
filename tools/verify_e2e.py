#!/usr/bin/env python
"""MatSelect 真机端到端验证（L0：真实进程 + 真实 HTTP + 真实静态资源）。

与 verify_api.py 的区别：那个用 TestClient（进程内 ASGI），本脚本
**真的启动 uvicorn 子进程**并用 httpx 走网络请求，用来验证：
  1. 应用能在真实进程里启动（lifespan 建库/播种不报错）
  2. 业务 API 真实可用
  3. `frontend/dist` 被正确挂载为 SPA（GET / 返回 index.html）

用法：
    cd D:\\Documents\\MyDoc\\CODE\\MatSelect\\backend
    & "...\\python.exe" ..\\tools\\verify_e2e.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx  # noqa: E402

PORT = int(os.environ.get("E2E_PORT", "8101"))
BASE = f"http://127.0.0.1:{PORT}"

# 独立临时库，避免污染 data/matselect.db
TMP_DB = Path(tempfile.gettempdir()) / "matselect_e2e.db"
for suffix in ("", "-wal", "-shm"):
    try:
        Path(str(TMP_DB) + suffix).unlink()
    except FileNotFoundError:
        pass

env = dict(os.environ)
env["MATSELECT_DB"] = str(TMP_DB)
env["PYTHONIOENCODING"] = "utf-8"

lines: list[str] = [f"===== MatSelect 真机端到端验证 =====  {BASE}  db={TMP_DB}", ""]
passed = failed = 0


def check(no: str, desc: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        lines.append(f"[OK  ] {no} {desc}  {detail}")
    else:
        failed += 1
        lines.append(f"[FAIL] {no} {desc}  {detail}")


proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
     "--port", str(PORT), "--log-level", "warning"],
    cwd=str(BACKEND),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

try:
    # 等待就绪（最多 40 秒）
    ready = False
    for _ in range(40):
        if proc.poll() is not None:
            break
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=2.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)

    check("E1", "uvicorn 子进程启动并就绪", ready,
          "已就绪" if ready else f"未就绪，进程退出码={proc.poll()}")

    if ready:
        r = httpx.get(f"{BASE}/api/health", timeout=5.0)
        d = r.json() if r.status_code == 200 else {}
        check("E2", "GET /api/health（真实 HTTP）",
              r.status_code == 200 and d.get("materials", 0) >= 50,
              f"HTTP {r.status_code} {d}")

        r = httpx.get(f"{BASE}/api/materials", params={"q": "PP", "page_size": 5}, timeout=5.0)
        d = r.json() if r.status_code == 200 else {}
        check("E3", "GET /api/materials?q=PP（<3 字符兜底）",
              r.status_code == 200 and d.get("total", 0) > 0,
              f"HTTP {r.status_code} total={d.get('total')}")

        r = httpx.post(f"{BASE}/api/recommend/run", timeout=15.0, json={
            "constraints": {"part_type": "电气件", "process": "注塑", "temp_limit": 150, "extra": ["阻燃"]}
        })
        d = r.json() if r.status_code == 200 else {}
        leak = [x["material"]["name"] for x in d.get("results", [])
                if (x["material"].get("service_temp_limit") or -1) < 150]
        check("E4", "POST /api/recommend/run（真实 HTTP，硬约束零越界）",
              r.status_code == 200 and not leak,
              f"HTTP {r.status_code} 结果={len(d.get('results', []))} 越界={leak}")

        # SPA：真实静态资源挂载
        r = httpx.get(f"{BASE}/", timeout=5.0)
        body = r.text if r.status_code == 200 else ""
        has_title = "MatSelect" in body
        has_asset = "/assets/" in body
        check("E5", "GET / 返回前端 SPA（dist 已挂载）",
              r.status_code == 200 and has_title and has_asset,
              f"HTTP {r.status_code} 含标题={has_title} 含资源引用={has_asset}")

        # SPA 深链回退（/materials 在浏览器刷新时应回落到 index.html）
        r = httpx.get(f"{BASE}/materials", timeout=5.0)
        check("E6", "GET /materials 深链回退到 SPA",
              r.status_code == 200 and "MatSelect" in r.text,
              f"HTTP {r.status_code}")

        # 404 错误体（真实 HTTP）
        r = httpx.get(f"{BASE}/api/materials/no-such-uid-000", timeout=5.0)
        eb = r.json() if r.status_code == 404 else {}
        check("E7", "真实 HTTP 404 → {error:{code,message}}",
              r.status_code == 404 and (eb.get("error") or {}).get("code") == "NOT_FOUND",
              f"HTTP {r.status_code} {eb}")
finally:
    proc.terminate()
    try:
        out = proc.communicate(timeout=10)[0].decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        proc.kill()
        out = ""
    if out.strip():
        lines.append("")
        lines.append("--- 服务端日志 ---")
        lines += out.strip().splitlines()[:20]

lines += ["", f"总计: 通过 {passed} / 失败 {failed}", "RESULT: " + ("PASS" if failed == 0 else "FAIL")]
report = ROOT / "tools" / "_verify_e2e.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
raise SystemExit(0 if failed == 0 else 1)
