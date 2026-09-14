# -*- coding: utf-8 -*-
"""
选型工作台验收（docs/plan/02 §4.3；doc/前端原型 05 §1.1 / §1.2；PRD §3 B5/B6/C1）

覆盖：选材主流程（含 ③→④ 不出结果、同任务同材料不重复入待选、skipped 不计失败）、
回评闭环（理由必填、语义拆解、命中/未命中分流）、待选面板增删改排序。
分享闭环见 test_api_data_io.py。后端未落地时由 conftest 干净 skip。
"""
import pytest


def _new_task(client, title="验收-选材主流程"):
    r = client.post("/api/tasks", json={"title": title})
    assert r.status_code == 200, f"建任务期望 200，实际 {r.status_code}：{r.text}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 选材主流程
# ---------------------------------------------------------------------------
def test_flow_step3_no_results_before_confirm(seeded_client):
    """P0 | §1.1 ③→④ 之间不许出结果：/api/recommend/parse 仅回显约束，不含 results。"""
    r = seeded_client.post("/api/recommend/parse",
                            json={"text": "保险丝座 注塑 150°C"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    assert "results" not in r.json(), "parse 阶段禁止返回推荐结果（须先确认约束）"


def test_flow_message_yields_constraints_and_reco(seeded_client):
    """P0 | ①→⑤ 发送需求 → 会话流返回约束回显 + 推荐结果（assistant 含 recommendations）。"""
    task_id = _new_task(seeded_client)
    r = seeded_client.post(f"/api/tasks/{task_id}/messages",
                            json={"text": "保险丝座组件，注塑，温度不超过150°C"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert "user" in body and "assistant" in body, f"期望 user+assistant，实际 {list(body)}"
    asst = body["assistant"]
    assert asst.get("constraints"), "assistant 应回显约束"
    assert asst.get("recommendations") or asst.get("results"), \
        "确认后应生成推荐结果（assistant.recommendations/results）"


def test_flow_shortlist_no_duplicate(seeded_client):
    """P0 | ⑥ 同任务同材料不重复入待选（UNIQUE(task_id, material_id)）。"""
    task_id = _new_task(seeded_client)
    uid = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    r1 = seeded_client.post(f"/api/tasks/{task_id}/shortlist",
                             json={"material_uid": uid, "tag": "key"})
    assert r1.status_code == 200, f"首次加入期望 200，实际 {r1.status_code}：{r1.text}"
    r2 = seeded_client.post(f"/api/tasks/{task_id}/shortlist",
                             json={"material_uid": uid, "tag": "key"})
    # 第二次：要么 200 幂等（仍是 1 条），要么 409 CONFLICT；绝不允许出现 2 条
    assert r2.status_code in (200, 409), f"期望 200/409，实际 {r2.status_code}：{r2.text}"
    lst = seeded_client.get(f"/api/tasks/{task_id}/shortlist").json()["items"]
    # 契约 §4.2 / 原型 §4：待选项响应体是 `ShortlistItem { id, material: MaterialCard, score, ... }`，
    # 材料 uid 位于嵌套的 material 上（`material_uid` 只是 POST 请求体字段名）。
    same = [it for it in lst if (it.get("material") or {}).get("uid") == uid]
    assert len(same) == 1, f"期望同材料仅 1 条，实际 {len(same)} 条"


def test_flow_followup_refreshes(seeded_client):
    """P1 | ⑦ 追问：同一任务再次发送 → 产生新 assistant 消息（刷新而非纯追加忽略）。"""
    task_id = _new_task(seeded_client)
    seeded_client.post(f"/api/tasks/{task_id}/messages", json={"text": "保险丝座 注塑 150°C"})
    r2 = seeded_client.post(f"/api/tasks/{task_id}/messages", json={"text": "再便宜点的方案"})
    assert r2.status_code == 200, f"期望 200，实际 {r2.status_code}：{r2.text}"
    assert "assistant" in r2.json(), "追问应返回新的 assistant 消息"


def test_flow_list_messages_time_ordered(seeded_client):
    """P1 | G2 §4.3 会话回放：GET /api/tasks/{id}/messages 按时间序返回 user + assistant。"""
    task_id = _new_task(seeded_client, title="验收-消息列表")
    seeded_client.post(f"/api/tasks/{task_id}/messages", json={"text": "保险丝座 注塑 150°C"})
    r = seeded_client.get(f"/api/tasks/{task_id}/messages")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    items = r.json()["items"]
    roles = [m.get("role") for m in items]
    assert "user" in roles and "assistant" in roles, f"期望含 user/assistant，实际 {roles}"
    assert roles.index("user") < roles.index("assistant"), "user 消息应早于 assistant 返回"


def test_flow_skip_not_counted_as_fail(seeded_client):
    """P0 | ⑧ skipped 不计失败：result=skipped 存储且不触发降权。"""
    task_id = _new_task(seeded_client)
    rp = seeded_client.post(f"/api/tasks/{task_id}/feedback", json={"result": "skipped"})
    assert rp.status_code == 200, f"期望 200，实际 {rp.status_code}：{rp.text}"
    assert rp.json().get("penalty_applied") is False, "skipped 不应降权"
    # GET 回评应反映 skipped（或 null），而非 fail
    rg = seeded_client.get(f"/api/tasks/{task_id}/feedback")
    assert rg.status_code == 200
    fb = rg.json()
    if fb:  # 非 null
        assert fb.get("result") == "skipped", f"期望 result=skipped，实际 {fb}"


def test_task_archive(seeded_client):
    """P1 | ⑨ 归档：PATCH status=archived 生效，且默认列表不再出现。"""
    task_id = _new_task(seeded_client)
    rp = seeded_client.patch(f"/api/tasks/{task_id}", json={"status": "archived"})
    assert rp.status_code == 200, f"期望 200，实际 {rp.status_code}：{rp.text}"
    assert rp.json().get("status") == "archived", "期望 status=archived"
    lst = seeded_client.get("/api/tasks", params={"status": "active"}).json()["items"]
    assert not any(t["id"] == task_id for t in lst), "归档后不应出现在 active 列表"


# ---------------------------------------------------------------------------
# 回评闭环
# ---------------------------------------------------------------------------
def test_feedback_reason_required(seeded_client):
    """P0 | §1.2 失败理由必填：result=fail 无 reason_text → VALIDATION_ERROR。"""
    task_id = _new_task(seeded_client)
    r = seeded_client.post(f"/api/tasks/{task_id}/feedback", json={"result": "fail"})
    assert r.status_code in (400, 422), f"期望 400/422，实际 {r.status_code}：{r.text}"
    if r.status_code == 400:
        assert r.json().get("error", {}).get("code") == "VALIDATION_ERROR"


def test_feedback_semantic_parse(seeded_client):
    """P0 | §1.2 语义拆解：返回 parsed{materials,dimensions,keywords,confidence}。"""
    task_id = _new_task(seeded_client)
    uid = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    r = seeded_client.post(f"/api/tasks/{task_id}/feedback",
                            json={"result": "fail", "reason_text": "PA66+GF30 价格与实际不符",
                                  "materials": [uid]})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    parsed = r.json().get("parsed", {})
    for k in ("materials", "dimensions", "keywords", "confidence"):
        assert k in parsed, f"期望 parsed 含 {k}，实际 parsed={parsed}"


def test_feedback_miss_writes_requirement_gap(seeded_client):
    """P0 | §1.2 未命中材料 → requirement_gap（知识盲区）。"""
    task_id = _new_task(seeded_client)
    r = seeded_client.post(f"/api/tasks/{task_id}/feedback",
                            json={"result": "fail",
                                  "reason_text": "都没有合适的，需要耐 300 度以上的特种料",
                                  "materials": []})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    # 知识盲区报告应出现对应维度/缺口
    g = seeded_client.get("/api/insights/gaps", params={"range": "all"})
    assert g.status_code == 200, f"期望 200，实际 {g.status_code}"
    items = g.json().get("items", [])
    assert any("温度" in (it.get("dimension") or "") or "耐温" in (it.get("suggestion") or "")
               for it in items), f"期望盲区报告含耐温缺口，实际 {items}"


# ---------------------------------------------------------------------------
# 待选面板：增删改 / 排序 / 备注
# ---------------------------------------------------------------------------
def test_shortlist_crud_and_order(seeded_client):
    """P1 | B6 待选：备注更新、排序、删除均生效。"""
    task_id = _new_task(seeded_client)
    u1 = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    u2 = seeded_client.get("/api/materials", params={"q": "PBT+GF30"}).json()["items"][0]["uid"]
    a = seeded_client.post(f"/api/tasks/{task_id}/shortlist", json={"material_uid": u1}).json()
    b = seeded_client.post(f"/api/tasks/{task_id}/shortlist", json={"material_uid": u2}).json()
    # 备注更新
    rn = seeded_client.patch(f"/api/shortlist/{a['id']}", json={"user_note": "样品待测"})
    assert rn.status_code == 200 and rn.json().get("user_note") == "样品待测", \
        f"期望备注保存，实际 {rn.json()}"
    # 排序
    ro = seeded_client.put(f"/api/tasks/{task_id}/shortlist/order",
                           json={"ids": [b["id"], a["id"]]})
    assert ro.status_code == 200, f"期望 200，实际 {ro.status_code}：{ro.text}"
    # 删除
    rd = seeded_client.delete(f"/api/shortlist/{a['id']}")
    assert rd.status_code == 200 and rd.json().get("ok") is True, f"期望 ok，实际 {rd.json()}"
    remain = seeded_client.get(f"/api/tasks/{task_id}/shortlist").json()["items"]
    assert len(remain) == 1, f"期望剩余 1 条，实际 {len(remain)}"
