# -*- coding: utf-8 -*-
"""
推荐算法验收（docs/plan/02 §4.2 / §5；doc/前端原型 05 §1.1；PRD §5）

重点验证「硬约束不过滤绝不出现」「空结果放宽 -10 且提示」「score<60 不进列表」
「5 维分解之和与总分一致」「单条负面反馈不降权 / 同维度 2 次才降权且幅度≤15」
「reason 数值零编造（来自库）」。
后端未落地时由 conftest 干净 skip。
"""
import pytest

THRESHOLD = 2          # 同维度降权生效阈值（契约 §5）
PENALTY_MAX = 15       # 单次最高降分（契约 §5 / 10 屏）
TEMP_RELAX_STEP = 10   # 空结果放宽步长（契约 §5.2）

DIM_ALIASES = {
    "temp": ["temp", "temperature", "temp_margin", "温度裕度", "温度"],
    "semantic": ["semantic", "semantic_similarity", "语义场景", "语义"],
    "cost": ["cost", "cost_match", "成本匹配", "成本"],
    "mechanics": ["mechanics", "mechanics_match", "力学性能", "力学"],
    "process": ["process", "process_match", "工艺适配", "工艺"],
    "feedback": ["feedback", "feedback_penalty", "反馈修正", "反馈"],
}


def _extract_dims(result):
    """从 Recommendation 解析 5 维得分（兼容 {dim:number} 与 {dim:{score,max}} 两种形状）。"""
    bd = result.get("breakdown") or result.get("score_breakdown")
    if not isinstance(bd, dict):
        return None
    out = {}
    for canon, aliases in DIM_ALIASES.items():
        val = None
        for a in aliases:
            if a in bd:
                v = bd[a]
                if isinstance(v, dict):
                    val = v.get("score") if "score" in v else v.get("achieved")
                else:
                    val = v
                break
        if val is not None:
            try:
                out[canon] = float(val)
            except (TypeError, ValueError):
                out[canon] = None
    return out


def _make_task(client, title="验收临时任务"):
    r = client.post("/api/tasks", json={"title": title})
    assert r.status_code == 200, f"建任务期望 200，实际 {r.status_code}：{r.text}"
    return r.json()["id"]


def _post_fail_feedback(client, task_id, uid, reason_text):
    """提交一次失败回评（命中指定材料），返回响应 JSON。"""
    payload = {
        "result": "fail",
        "reason_text": reason_text,
        "reason_tags": ["价格与实际不符"],
        "materials": [uid],
    }
    r = client.post(f"/api/tasks/{task_id}/feedback", json=payload)
    assert r.status_code == 200, f"回评期望 200，实际 {r.status_code}：{r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# 约束抽取
# ---------------------------------------------------------------------------
def test_recommend_parse_constraints(seeded_client):
    """P0 | B1 约束抽取：'保险丝座 注塑 150°C' → process=注塑、temp_limit=150。"""
    r = seeded_client.post("/api/recommend/parse",
                            json={"text": "我想做一个保险丝座组件，注塑件，温度不超过150°C"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    c = r.json().get("constraints", {})
    assert c.get("temp_limit") == 150, f"期望 temp_limit=150，实际 {c.get('temp_limit')}"
    assert "注塑" in (c.get("process") or ""), f"期望 process 含'注塑'，实际 {c.get('process')}"


def test_recommend_parse_degraded_when_nothing(seeded_client):
    """P1 | B1 降级：完全无法抽取的文本 → degraded=true。"""
    r = seeded_client.post("/api/recommend/parse", json={"text": "随便聊聊今天天气不错"})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}"
    assert r.json().get("degraded") is True, "未命中任何约束应 degraded=true"


# ---------------------------------------------------------------------------
# 硬约束过滤：不满足温度的材料绝不出现
# ---------------------------------------------------------------------------
def test_recommend_hard_filter_no_under_temp(seeded_client):
    """P0 | §5.2 硬约束：未放宽时，service_temp_limit < temp_limit 的材料绝不出现。"""
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"part_type": "电气件", "process": "注塑",
                                                  "temp_limit": 150}})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert not body.get("relaxed"), f"期望未放宽（relaxed 空），实际 {body.get('relaxed')}"
    for rec in body["results"]:
        m = rec.get("material") or rec
        limit = m.get("service_temp_limit")
        assert limit is not None and limit >= 150, \
            (f"期望所有结果 service_temp_limit>=150，"
             f"{m.get('name')} 的 limit={limit}")


# ---------------------------------------------------------------------------
# 空结果放宽 -10 且提示
# ---------------------------------------------------------------------------
def test_recommend_relax_on_empty(seeded_client):
    """P0 | §5.2 空结果放宽：temp_limit 远超上限 → 放宽 -10 记录，且提示含放宽后温度。"""
    high = 9999
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"process": "注塑", "temp_limit": high}})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    body = r.json()
    assert body.get("degraded") is True, "空结果应 degraded=true"
    relaxed = body.get("relaxed") or []
    assert relaxed, f"期望 relaxed 非空（记录放宽项），实际 {relaxed}"
    # 放宽步长应为 -10（契约 §5.2），提示中须出现放宽后的温度值
    expected_relaxed_temp = high - TEMP_RELAX_STEP
    assert any(str(expected_relaxed_temp) in str(item) for item in relaxed), \
        f"期望放宽提示含温度 {expected_relaxed_temp}，实际 relaxed={relaxed}"


# ---------------------------------------------------------------------------
# score<60 不进入列表
# ---------------------------------------------------------------------------
def test_recommend_score_floor(seeded_client):
    """P0 | §5 门槛：结果列表内 score 均 ≥ 60。"""
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"process": "注塑", "temp_limit": 120}})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    for rec in r.json()["results"]:
        score = rec.get("score") or rec.get("match_score")
        assert score is not None and score >= 60, \
            f"期望 score>=60，实际 {score}（{rec.get('material', {}).get('name')}）"


# ---------------------------------------------------------------------------
# 5 维分解之和与总分一致
# ---------------------------------------------------------------------------
def test_recommend_breakdown_sum_consistent(seeded_client):
    """P0 | §4 可解释：5 维分解之和（减反馈修正）≈ 总分（允许±1 取整误差）。"""
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"process": "注塑", "temp_limit": 150}})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    results = r.json()["results"]
    assert results, "期望有推荐结果用于校验分解"
    for rec in results:
        dims = _extract_dims(rec)
        score = rec.get("score")
        assert dims is not None, \
            f"期望含 5 维 breakdown，实际推荐体={rec}"
        five = [d for k, d in dims.items() if k in DIM_ALIASES and k != "feedback" and d is not None]
        assert len(five) == 5, f"期望解析出 5 个维度，实际 {dims}"
        fb = dims.get("feedback") or 0
        s = sum(five)
        assert abs(s - fb - score) <= 1.0, \
            f"期望 5维之和({s}) - 反馈({fb}) ≈ 总分({score})，偏差超 1"


# ---------------------------------------------------------------------------
# reason 数值零编造（来自库）
# ---------------------------------------------------------------------------
def test_recommend_reason_references_real_data(seeded_client):
    """P0 | §5.4 解释：reason 必须引用库中真实存在的材料名（零编造）。"""
    r = seeded_client.post("/api/recommend/run",
                            json={"constraints": {"process": "注塑", "temp_limit": 150}})
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}：{r.text}"
    results = r.json()["results"]
    assert results, "期望有结果"
    for rec in results:
        reason = rec.get("reason") or rec.get("reason_text") or ""
        name = (rec.get("material") or rec).get("name", "")
        assert reason.strip(), f"期望 reason 非空，实际为空（{name}）"
        # reason 至少应提及该材料名（库中存在），作为零编造的强信号
        assert name in reason, f"期望 reason 引用材料名'{name}'，实际 reason={reason!r}"


# ---------------------------------------------------------------------------
# 负面反馈：单条不降权 / 同维度 2 次才降权且幅度≤15
# ---------------------------------------------------------------------------
def test_feedback_single_no_penalty(seeded_client):
    """P0 | C1 防误伤：单条负面反馈 penalty_applied=False（不降权）。"""
    uid = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    task_id = _make_task(seeded_client)
    resp = _post_fail_feedback(seeded_client, task_id, uid, "PA66+GF30 价格与实际不符，采购价偏高")
    assert resp.get("penalty_applied") is False, \
        f"单条反馈期望 penalty_applied=False，实际 {resp.get('penalty_applied')}"


def test_feedback_two_hits_penalty_and_ceiling(seeded_client):
    """P0 | C1 降权：同维度 2 次 → penalty_applied=True，且降分幅度≤PENALTY_MAX(15)。"""
    uid = seeded_client.get("/api/materials", params={"q": "PA66+GF30"}).json()["items"][0]["uid"]
    task_id = _make_task(seeded_client)
    _post_fail_feedback(seeded_client, task_id, uid, "PA66+GF30 价格比库里高很多")
    resp2 = _post_fail_feedback(seeded_client, task_id, uid, "PA66+GF30 报价还是不对，成本超标")
    assert resp2.get("penalty_applied") is True, \
        f"同维度 2 次期望 penalty_applied=True，实际 {resp2.get('penalty_applied')}"
    # 降分幅度：若推荐结果暴露 feedback 修正分量，须 ≤ PENALTY_MAX
    rr = seeded_client.post("/api/recommend/run",
                             json={"constraints": {"process": "注塑", "temp_limit": 150},
                                   "task_id": task_id})
    if rr.status_code == 200:
        for rec in rr.json()["results"]:
            if (rec.get("material") or rec).get("uid") == uid:
                dims = _extract_dims(rec)
                if dims and dims.get("feedback") is not None:
                    assert -dims["feedback"] <= PENALTY_MAX, \
                        f"期望降分幅度≤{PENALTY_MAX}，实际 feedback={dims['feedback']}"
                break
