# -*- coding: utf-8 -*-
"""选型工作台业务服务：任务会话 / 待选清单 / 回评闭环 / 知识盲区。

对应 PRD B5（选型任务）、B6（待选清单）、C1（回评与反馈闭环）、F2（操作日志）。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.errors import not_found, validation_error
from app.core.logging import write_log
from app.repository import (
    feedback_repo,
    material_repo,
    shortlist_repo,
    task_repo,
)
from app.services import material_service, recommend_service

_TZ = timezone(timedelta(hours=8))

# 回评理由 → 问题维度的关键词映射（PRD C1 第 3 步「语义拆解」）
DIMENSION_KEYWORDS = {
    "价格不符": ["价格", "贵", "便宜", "报价", "采购价", "成本", "元/kg", "钱"],
    "温度不符": ["温度", "耐温", "高温", "低温", "℃", "°c", "工况", "太热"],
    "工艺不符": ["工艺", "成型", "注塑", "挤出", "压铸", "加工"],
    "参数准确性": ["参数", "数值", "数据", "不对", "有误", "错误", "差太多"],
    "材料信息缺失": ["缺失", "查不到", "没有信息", "资料少", "不全"],
    "外观": ["外观", "表面", "毛边", "浮纤", "色差", "缩痕"],
}


# ---------------------------------------------------------------- 任务 / 会话


def list_tasks(status: Optional[str] = None, q: Optional[str] = None) -> List[dict]:
    return task_repo.list_tasks(status=status, q=q)


def create_task(title: Optional[str] = None) -> dict:
    return task_repo.create(title or "")


def patch_task(task_id: int, title=None, pinned=None, status=None) -> dict:
    task = task_repo.patch(int(task_id), title=title, pinned=pinned, status=status)
    if status:
        write_log("归档任务" if status == "archived" else "更新任务", task.get("title") or "", {"id": task_id})
    return task


def list_messages(task_id: int) -> List[dict]:
    return task_repo.list_messages(int(task_id))


def _merge_constraints(prev: Optional[dict], cur: dict) -> dict:
    """追问时沿用本任务上下文：新抽取到的项覆盖旧项，未抽取到的保留旧值。"""
    prev = prev or {}
    out = dict(prev)
    for k in ("part_type", "process", "temp_limit"):
        if cur.get(k) is not None:
            out[k] = cur[k]
    extra = list(dict.fromkeys(list(prev.get("extra") or []) + list(cur.get("extra") or [])))
    out["extra"] = extra
    return out


def _reweight_note(text: str, prev: Optional[dict], merged: dict) -> str:
    low = (text or "").lower()
    if any(k in low for k in ("便宜", "成本", "降本", "省钱", "预算")):
        return "已按「成本敏感」重新加权"
    if "阻燃" in low or "防火" in low:
        return "已追加「阻燃」约束并重新推荐"
    if any(k in low for k in ("耐温", "温度", "℃", "高温")):
        return "已更新温度约束并重新推荐"
    if prev:
        return "已结合本任务上下文重新解析并刷新推荐"
    return ""


def send_message(task_id: int, text: str) -> dict:
    """追问 / 首次输入：写入用户消息，重解析 → 重跑推荐 → 写入 assistant 消息。

    首次输入且任务无标题时，用输入前 12 字作为任务标题（PRD B5）。
    """
    text = (text or "").strip()
    if not text:
        raise validation_error("请输入需求描述")
    task = task_repo.require(int(task_id))

    if (task.get("title") or "") in ("", "新选型任务"):
        task_repo.patch(task["id"], title=text[:12])

    user_msg = task_repo.add_message(task["id"], "user", {"text": text})

    prev_msg = task_repo.last_assistant_message(task["id"])
    prev_constraints = (prev_msg or {}).get("constraints") if prev_msg else None

    is_followup = prev_msg is not None
    if is_followup:
        parsed_new = recommend_service.parse(text, task_id=task["id"])
        constraints = _merge_constraints(prev_constraints, parsed_new["constraints"])
        confidence = parsed_new["confidence"]
        degraded = bool(parsed_new["degraded"] and not prev_constraints)
    else:
        parsed_new = recommend_service.parse(text, task_id=task["id"])
        constraints = parsed_new["constraints"]
        confidence = parsed_new["confidence"]
        degraded = parsed_new["degraded"]

    run_result = recommend_service.run(constraints, task_id=task["id"], user_text=text)

    payload = {
        "text": "",
        "constraints": constraints,
        "confidence": confidence,
        "degraded": bool(degraded) or run_result["degraded"],
        "results": run_result["results"],
    }
    if run_result["relaxed"]:
        payload["relax_note"] = "；".join(run_result["relaxed"])
    note = _reweight_note(text, prev_constraints, constraints)
    if note:
        payload["reweight_note"] = note

    assistant_msg = task_repo.add_message(task["id"], "assistant", payload)
    return {"user": user_msg, "assistant": assistant_msg}


# ---------------------------------------------------------------- 待选清单


def _score_index(task_id: int) -> dict:
    """从该任务最近一次推荐结果建立 {uid: score} 索引。"""
    out = {}
    for r in task_repo.recent_results(int(task_id)):
        try:
            out[r["material"]["uid"]] = r.get("score", 0)
        except (KeyError, TypeError):
            continue
    return out


def _decorate(item: dict, scores: dict) -> dict:
    detail = material_repo.get_material_by_id(item["material_id"])
    return {
        "id": item["id"],
        "material": material_service.to_card(detail) if detail else {},
        "score": scores.get(detail["uid"] if detail else "", 0),
        "user_note": item.get("user_note") or "",
        "tag": item.get("tag") or "candidate",
        "sort_order": item.get("sort_order") or 0,
        "added_at": item.get("added_at"),
    }


def list_shortlist(task_id: int) -> List[dict]:
    task_repo.require(int(task_id))
    scores = _score_index(int(task_id))
    return [_decorate(i, scores) for i in shortlist_repo.list_items(int(task_id))]


def add_shortlist(task_id: int, material_uid: str, tag: Optional[str] = None) -> dict:
    task_repo.require(int(task_id))
    mid = material_repo.get_material_id(material_uid)
    if mid is None:
        raise not_found("材料不存在")
    item = shortlist_repo.add(int(task_id), mid, tag)  # 幂等：已存在则返回既有项
    write_log("加入待选", material_uid, {"task_id": task_id})
    return _decorate(item, _score_index(int(task_id)))


def patch_shortlist(item_id: int, user_note=None, tag=None) -> dict:
    item = shortlist_repo.patch(int(item_id), user_note=user_note, tag=tag)
    return _decorate(item, _score_index(item["task_id"]))


def reorder_shortlist(task_id: int, ids: List[int]) -> List[dict]:
    task_repo.require(int(task_id))
    shortlist_repo.set_order(int(task_id), ids)
    return list_shortlist(int(task_id))


def remove_shortlist(item_id: int) -> dict:
    shortlist_repo.delete(int(item_id))
    return {"ok": True}


# ---------------------------------------------------------------- 回评闭环


def _extract_materials(text: str, task_id: Optional[int]) -> List[str]:
    """从理由文本 + 本次推荐列表中识别涉及材料的名称。"""
    found: List[str] = []
    low = (text or "").lower()
    if task_id:
        for r in task_repo.recent_results(int(task_id)):
            name = ((r or {}).get("material") or {}).get("name") or ""
            short = ((r or {}).get("material") or {}).get("short_name") or ""
            if name and (name.lower() in low or (short and short.lower() in low)):
                found.append(name)
    return list(dict.fromkeys(found))


def _extract_dimensions(text: str, reason_tags: List[str]) -> List[str]:
    dims: List[str] = []
    low = (text or "").lower()
    for dim, kws in DIMENSION_KEYWORDS.items():
        if any(k.lower() in low for k in kws):
            dims.append(dim)
    # 数值型温度表达（「需要耐 300 度以上」「180℃ 就失效」）：
    # 关键词表的「耐温/高温」是连续词，覆盖不到数字夹在中间的中文写法，
    # 漏判会把温度类盲区错误归到兜底的「材料信息缺失」（PRD C1 盲区看板维度失真）。
    if "温度不符" not in dims and re.search(r"\d{2,4}\s*(?:°\s*c|℃|度|摄氏度)", low):
        dims.append("温度不符")
    # 用户勾选的问题类型也映射到维度（① 无满足材料 ② 不相关 ③ 参数有误 ④ 价格不符 ⑤ 信息缺失 ⑥ 其他）
    tag_map = {
        "①": "材料信息缺失", "②": "材料信息缺失", "③": "参数准确性",
        "④": "价格不符", "⑤": "材料信息缺失",
    }
    for t in reason_tags or []:
        for k, dim in tag_map.items():
            if k in str(t) and dim not in dims:
                dims.append(dim)
    return dims


def _extract_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text or "")
    stop = {"这个", "那个", "我们", "他们", "但是", "因为", "所以", "还是", "就是", "没有", "不是"}
    return [t for t in tokens if t not in stop][:8]


def submit_feedback(task_id: int, payload: dict) -> dict:
    """回评：success / fail / skipped。

    fail → 语义拆解 → 命中具体材料写 material_negative_feedback；未命中写 requirement_gap。
    skipped 与「不回评」均不计入成功/失败率。
    """
    task = task_repo.require(int(task_id))
    result = (payload or {}).get("result")
    if result not in ("success", "fail", "skipped"):
        raise validation_error("result 仅支持 success / fail / skipped")

    reason_text = (payload or {}).get("reason_text") or ""
    reason_tags = (payload or {}).get("reason_tags") or []
    material_uids = (payload or {}).get("material_uids") or []

    if result == "fail" and not reason_text.strip():
        raise validation_error("请填写失败理由")

    parsed = {"materials": [], "dimensions": [], "keywords": [], "confidence": 0.0}
    if result == "fail":
        materials = _extract_materials(reason_text, task["id"])
        if material_uids:
            names = []
            for uid in material_uids:
                d = material_repo.get_material(uid)
                if d:
                    names.append(d["name"])
            materials = list(dict.fromkeys(materials + names))
        dims = _extract_dimensions(reason_text, reason_tags) or ["材料信息缺失"]
        kws = _extract_keywords(reason_text)
        conf = round(min(1.0, (len(materials) * 0.4 + len(dims) * 0.3 + 0.1)), 2)
        parsed = {"materials": materials, "dimensions": dims, "keywords": kws, "confidence": conf}

    fid = feedback_repo.insert_feedback(task["id"], result, reason_text, reason_tags, parsed)

    penalty_applied = False
    if result == "fail":
        if parsed["materials"]:
            for name in parsed["materials"]:
                uid = _find_uid_by_name(name)
                if not uid:
                    continue
                mid = material_repo.get_material_id(uid)
                for dim in parsed["dimensions"]:
                    feedback_repo.insert_negative(mid, dim, reason_text, fid)
                hits = feedback_repo.hits_by_material(mid)
                threshold = _threshold()
                if any(c >= threshold for c in hits.values()):
                    penalty_applied = True
        else:
            feedback_repo.insert_gap(task["id"], reason_text, parsed)

    write_log("回评", task.get("title") or "", {"task_id": task["id"], "result": result})
    return {"parsed": parsed, "penalty_applied": penalty_applied, "feedback_id": fid}


def _threshold() -> int:
    from app.repository.settings_repo import get_penalty

    return int(get_penalty()["threshold"])


def _find_uid_by_name(name: str) -> Optional[str]:
    from app.repository.base import query_one

    row = query_one("SELECT uid FROM material WHERE name=? OR short_name=?", (name, name))
    return row["uid"] if row else None


def get_task_feedback(task_id: int):
    task_repo.require(int(task_id))
    return feedback_repo.latest_feedback(int(task_id))


def list_my_feedback() -> List[dict]:
    return feedback_repo.list_negative_settings(only_active=True)


def clear_my_feedback() -> dict:
    feedback_repo.clear_negative()
    write_log("清空我的反馈")
    return {"ok": True}


# ---------------------------------------------------------------- 知识盲区


_RANGE_DAYS = {"week": 7, "month": 30, "all": None}


def _suggestion(dim: str) -> str:
    return {
        "价格不符": "核对并更新该类材料的参考价区间（供应商最新报价）",
        "温度不符": "补充低温/高温工况可用材料，或在词典中补充温度表达的同义说法",
        "工艺不符": "补充该成型工艺的材料，或在术语词典中补充工艺同义词",
        "参数准确性": "抽检并修正相关材料的参数来源与数值",
        "材料信息缺失": "补充该类需求的材料条目（当前库覆盖不足）",
        "外观": "补充外观要求相关的特性标签与注意事项",
    }.get(dim, "按该维度补充数据或术语")


def gaps(range_key: str = "week") -> List[dict]:
    since = None
    days = _RANGE_DAYS.get(range_key, 7)
    if days:
        since = (datetime.now(_TZ) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    rows = feedback_repo.list_gaps(since)
    counter: dict[str, int] = {}
    for r in rows:
        for dim in ((r.get("parsed") or {}).get("dimensions") or ["材料信息缺失"]):
            counter[dim] = counter.get(dim, 0) + 1
    out = [
        {"dimension": dim, "count": cnt, "suggestion": _suggestion(dim)}
        for dim, cnt in sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return out
