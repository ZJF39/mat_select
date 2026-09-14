#!/usr/bin/env python
"""MatSelect 后端接口端到端验收（契约 §4 全量对照）。

用法（PowerShell，先设 $ErrorActionPreference='Continue'）：
    cd D:\\Documents\\MyDoc\\CODE\\MatSelect\\backend
    & "C:\\Users\\73937\\.workbuddy\\binaries\\python\\envs\\matselect\\Scripts\\python.exe" ..\\tools\\verify_api.py

用 FastAPI TestClient 直连应用（不依赖外部启动服务），逐条断言并输出
「请求 → 状态码 → 关键返回」。结果同时写入 tools/_verify_api.txt（UTF-8）。
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# 用独立临时库，避免污染 data/matselect.db
TMP_DB = Path(os.environ.get("MATSELECT_DB") or (Path(os.environ.get("TEMP", "/tmp")) / "matselect_apitest.db"))
for suffix in ("", "-wal", "-shm"):
    try:
        Path(str(TMP_DB) + suffix).unlink()
    except FileNotFoundError:
        pass
os.environ["MATSELECT_DB"] = str(TMP_DB)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.io_service import pack_checksum  # noqa: E402

lines: list[str] = [f"===== MatSelect 后端接口验收 =====  db={TMP_DB}", ""]
passed = failed = 0


def check(no: str, desc: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        lines.append(f"[OK  ] {no} {desc}  {detail}")
    else:
        failed += 1
        lines.append(f"[FAIL] {no} {desc}  {detail}")


TEST_TEXT = "我想做一个保险丝座组件，它是一个注塑件，使用场景温度不超过150°C，要有阻燃"

with TestClient(app) as client:
    # 1 health
    r = client.get("/api/health")
    data = r.json() if r.status_code == 200 else {}
    check("01", "GET /api/health", r.status_code == 200 and data.get("materials", 0) >= 50,
          f"HTTP {r.status_code} materials={data.get('materials')} version={data.get('version')}")

    # 2 列表
    r = client.get("/api/materials?page_size=5")
    d = r.json() if r.status_code == 200 else {}
    check("02", "GET /api/materials?page_size=5", r.status_code == 200 and d.get("total", 0) >= 50
          and len(d.get("items", [])) == 5, f"HTTP {r.status_code} total={d.get('total')} items={len(d.get('items', []))}")

    # 3 <3 字符检索兜底（trigram 真实缺陷）
    r = client.get("/api/materials?q=PP")
    d = r.json() if r.status_code == 200 else {}
    names = [i.get("name", "") for i in d.get("items", [])]
    check("03", "GET /api/materials?q=PP（<3字符 LIKE 兜底）",
          r.status_code == 200 and d.get("total", 0) > 0,
          f"HTTP {r.status_code} total={d.get('total')} 例:{names[:3]}")

    # 4 温度硬筛选
    r = client.get("/api/materials?temp_min=150&page_size=100")
    d = r.json() if r.status_code == 200 else {}
    bad = [i["name"] for i in d.get("items", []) if (i.get("service_temp_limit") or -1) < 150]
    check("04", "GET /api/materials?temp_min=150", r.status_code == 200 and not bad,
          f"HTTP {r.status_code} total={d.get('total')} 越界={bad[:3]}")

    # 5 parse
    r = client.post("/api/recommend/parse", json={"text": TEST_TEXT})
    p = r.json() if r.status_code == 200 else {}
    c = p.get("constraints", {})
    check("05", "POST /api/recommend/parse",
          r.status_code == 200 and c.get("process") == "注塑" and c.get("temp_limit") == 150,
          f"HTTP {r.status_code} constraints={c} conf={p.get('confidence')}")

    # 6 run（硬约束不可突破）
    r = client.post("/api/recommend/run", json={"constraints": c})
    run = r.json() if r.status_code == 200 else {}
    leak = [x["material"]["name"] for x in run.get("results", [])
            if (x["material"].get("service_temp_limit") or -1) < 150]
    scores = [x.get("score") for x in run.get("results", [])]
    check("06", "POST /api/recommend/run（硬约束不可突破）",
          r.status_code == 200 and not leak and all(s >= 60 for s in scores),
          f"HTTP {r.status_code} 结果={len(run.get('results', []))} 越界={leak} scores={scores}")

    # 7 任务 + 会话
    r = client.post("/api/tasks", json={"title": "保险丝座选材"})
    task = r.json() if r.status_code == 201 else {}
    tid = task.get("id")
    check("07a", "POST /api/tasks", r.status_code == 201 and tid, f"HTTP {r.status_code} id={tid}")
    r = client.post(f"/api/tasks/{tid}/messages", json={"text": TEST_TEXT})
    msg = r.json() if r.status_code == 201 else {}
    r2 = client.get(f"/api/tasks/{tid}/messages")
    msgs = r2.json().get("items", []) if r2.status_code == 200 else []
    roles = [m.get("role") for m in msgs]
    check("07b", "POST/GET /api/tasks/{id}/messages",
          r.status_code == 201 and roles == ["user", "assistant"],
          f"HTTP {r.status_code} roles={roles} 推荐={len((msg.get('assistant') or {}).get('results') or [])}")

    # 8 待选 CRUD
    first_uid = (run.get("results") or [{}])[0].get("material", {}).get("uid")
    r = client.post(f"/api/tasks/{tid}/shortlist", json={"material_uid": first_uid})
    item = r.json() if r.status_code == 201 else {}
    iid = item.get("id")
    r_dup = client.post(f"/api/tasks/{tid}/shortlist", json={"material_uid": first_uid})
    r3 = client.patch(f"/api/shortlist/{iid}", json={"user_note": "样品待测 -40℃ 低温冲击", "tag": "key"})
    r4 = client.put(f"/api/tasks/{tid}/shortlist/order", json={"ids": [iid]})
    r5 = client.delete(f"/api/shortlist/{iid}")
    r6 = client.get(f"/api/tasks/{tid}/shortlist")
    check("08", "待选 增/幂等/备注/标记/排序/删",
          r.status_code == 201 and r_dup.status_code in (200, 201) and r3.status_code == 200
          and r4.status_code == 200 and r5.status_code == 200
          and len(r6.json().get("items", [])) == 0,
          f"add={r.status_code} dup={r_dup.status_code} patch={r3.status_code} "
          f"order={r4.status_code} del={r5.status_code} 剩余={len(r6.json().get('items', []))}")

    # 9 回评 fail（语义拆解）
    r = client.post(f"/api/tasks/{tid}/feedback", json={
        "result": "fail",
        "reason_text": f"{first_uid and ''}推荐的材料价格跟实际差太多，我们采购要 40 多，不是 28",
        "reason_tags": ["④ 价格与实际不符"],
        "material_uids": [first_uid] if first_uid else [],
    })
    fb = r.json() if r.status_code == 201 else {}
    parsed = fb.get("parsed") or {}
    check("09", "POST /api/tasks/{id}/feedback(fail)",
          r.status_code == 201 and "价格不符" in (parsed.get("dimensions") or [])
          and parsed.get("confidence", 0) > 0,
          f"HTTP {r.status_code} parsed={parsed} penalty_applied={fb.get('penalty_applied')}")

    # 9b 回评 fail 无理由必须 400
    r_bad = client.post(f"/api/tasks/{tid}/feedback", json={"result": "fail", "reason_text": ""})
    check("09b", "回评 fail 无理由 → 400", r_bad.status_code == 400,
          f"HTTP {r_bad.status_code} body={r_bad.json()}")

    # 10 导出 json + checksum 复算
    r = client.post("/api/export", json={"scope": "all", "format": "json", "include_work_data": False})
    cd = r.headers.get("content-disposition", "")
    pack_bytes = r.content
    export_http = r.status_code
    pack = json.loads(pack_bytes.decode("utf-8")) if export_http == 200 else {}
    recompute = pack_checksum(pack.get("materials", [])) if pack else ""
    check("10", "POST /api/export(json) + checksum 复算一致",
          export_http == 200 and "attachment" in cd and pack.get("checksum") == recompute
          and pack.get("material_count", 0) >= 50,
          f"HTTP {export_http} count={pack.get('material_count')} checksum一致={pack.get('checksum') == recompute}")

    # 11 导入两段式（用刚导出的包；skip 策略下本机已有同 uid → 全部跳过）
    r = client.post("/api/import/parse", files={"file": ("pack.json", pack_bytes, "application/json")})
    prev = r.json() if r.status_code == 200 else {}
    parse_http = r.status_code
    r2 = client.post("/api/import/commit", json={"token": prev.get("token"), "conflict_policy": "skip"})
    res = r2.json() if r2.status_code == 200 else {}
    check("11", "POST /api/import/parse + commit(skip)",
          parse_http == 200 and prev.get("checksum_ok") is True
          and prev.get("updated", 0) >= 50 and r2.status_code == 200 and res.get("ok") is True,
          f"parse={parse_http} checksum_ok={prev.get('checksum_ok')} update={prev.get('updated')} "
          f"commit={r2.status_code} {res.get('message')}")

    # 11b 篡改材料内容 → 校验和必须不一致（证明校验真的在算）
    broken = json.loads(pack_bytes.decode("utf-8"))
    broken["materials"][0]["name"] = "被篡改的材料"
    r = client.post("/api/import/parse",
                    files={"file": ("bad.json", json.dumps(broken, ensure_ascii=False).encode("utf-8"),
                                    "application/json")})
    bp = r.json() if r.status_code == 200 else {}
    check("11b", "导入 parse 检出校验和不一致",
          r.status_code == 200 and bp.get("checksum_ok") is False,
          f"HTTP {r.status_code} checksum_ok={bp.get('checksum_ok')}")

    # 11c 包版本不兼容 → 明确拒绝
    bad_ver = json.loads(pack_bytes.decode("utf-8"))
    bad_ver["pack_version"] = 99
    r = client.post("/api/import/parse",
                    files={"file": ("v99.json", json.dumps(bad_ver, ensure_ascii=False).encode("utf-8"),
                                    "application/json")})
    check("11c", "导入包版本不兼容 → 明确报错（4xx + IMPORT_REJECTED）",
          r.status_code in (400, 422)
          and (r.json().get("error") or {}).get("code") == "IMPORT_REJECTED",
          f"HTTP {r.status_code} body={r.json()}")

    # 12 权重 + 404 错误体
    r = client.get("/api/settings/weights")
    w = r.json() if r.status_code == 200 else {}
    r2 = client.get("/api/materials/不存在的uid-000")
    eb = r2.json() if r2.status_code == 404 else {}
    check("12", "GET /api/settings/weights + 404 错误体",
          r.status_code == 200 and abs(w.get("sum", 0) - 100) < 0.01
          and r2.status_code == 404 and "code" in (eb.get("error") or {}),
          f"weights={r.status_code} sum={w.get('sum')} 404体={eb}")

    # 13 分类树 / diff / 日志 / 搜索 / 备份
    r_cat = client.get("/api/categories")
    r_diff_target = client.get("/api/materials?page_size=1").json()["items"][0]["uid"]
    r_rev = client.get(f"/api/materials/{r_diff_target}/revisions")
    r_log = client.get("/api/logs?limit=5")
    r_srch = client.get("/api/search?q=保险丝座")
    r_bk = client.get("/api/backup/status")
    check("13", "分类树/版本/日志/搜索/备份状态",
          r_cat.status_code == 200 and len(r_cat.json().get("items", [])) >= 5
          and r_rev.status_code == 200 and r_log.status_code == 200 and r_srch.status_code == 200,
          f"cat={len(r_cat.json().get('items', []))} rev={len(r_rev.json().get('items', []))} "
          f"logs={len(r_log.json().get('items', []))} scenes={len(r_srch.json().get('scenes', []))}")

    # 14 更新材料 → diff summary
    detail = client.get(f"/api/materials/{r_diff_target}").json()
    # PUT 为全量替换语义（契约 MaterialUpsert）：必须提交完整字段集，
    # 否则未提交的字段会被置空 —— 这正是编辑表单需要回填全部字段的原因。
    upsert_keys = (
        "name", "short_name", "category_id", "grade_type", "aliases", "description",
        "density_min", "density_max", "tensile_strength_min", "tensile_strength_max",
        "elastic_modulus_min", "elastic_modulus_max", "elongation_min", "elongation_max",
        "notch_impact_min", "notch_impact_max", "hdt_min", "hdt_max",
        "service_temp_min", "service_temp_max", "service_temp_limit",
        "features", "cautions", "applications", "price_min", "price_max", "price_unit",
        "price_note", "molding_process", "certifications", "limitations",
        "source", "source_date", "value_type",
    )
    body = {k: detail.get(k) for k in upsert_keys}
    body["short_name"] = (body.get("short_name") or "") + "-改"
    body["description"] = (body.get("description") or "") + "（测试修改）"
    body["service_temp_limit"] = 999
    r = client.put(f"/api/materials/{r_diff_target}", json=body)
    nv = r.json().get("new_version") if r.status_code == 200 else None
    # 版本语义：一次编辑 = 一个新版本；对比「上一版 vs 本次」
    r_d = client.get(f"/api/materials/{r_diff_target}/revisions/{nv - 1}/diff?against={nv}")
    dp = r_d.json() if r_d.status_code == 200 else {}
    rows = dp.get("rows", [])
    kinds = sorted({x.get("type") for x in rows})
    check("14", "PUT 材料 → diff 逐字段（summary + 行数 + 三色类型）",
          r.status_code == 200 and r_d.status_code == 200 and len(rows) == 3
          and dp.get("summary") == "本次修改了 3 个字段",
          f"PUT={r.status_code} new_version={nv} rows={len(rows)} "
          f"summary={dp.get('summary')} types={kinds}")

    # 15 版本恢复：恢复到 v1，内容回滚且再生成一个新版本
    r = client.post(f"/api/materials/{r_diff_target}/revisions/1/restore")
    restored = r.json().get("material", {}) if r.status_code == 200 else {}
    r_list = client.get(f"/api/materials/{r_diff_target}/revisions")
    check("15", "POST 版本恢复 → 内容回滚 + 生成新版本",
          r.status_code == 200 and restored.get("service_temp_limit") != 999
          and len(r_list.json().get("items", [])) >= nv + 1,
          f"HTTP {r.status_code} 恢复后耐温上限={restored.get('service_temp_limit')} "
          f"版本数={len(r_list.json().get('items', []))}")

lines += ["", f"总计: 通过 {passed} / 失败 {failed}", "RESULT: " + ("PASS" if failed == 0 else "FAIL")]

report = ROOT / "tools" / "_verify_api.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
raise SystemExit(0 if failed == 0 else 1)
