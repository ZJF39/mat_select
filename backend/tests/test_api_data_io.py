# -*- coding: utf-8 -*-
"""
数据导出/导入验收（docs/plan/02 §4.4 / §4.6；doc/前端原型 05 §1.3 / §2；PRD §3 E1/E2）

覆盖：导出 JSON/md、checksum 往返一致、导入三段式（parse→commit）、
三种冲突策略（skip/overwrite/duplicate）、校验失败拒绝写库且不产生半截数据。
后端未落地时由 conftest 干净 skip。
"""
import hashlib
import json
import os
import tempfile
import uuid

import pytest


def pack_checksum(materials):
    """契约 §4.6 校验和算法（与生成端必须完全一致）。"""
    canonical = json.dumps(materials, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _export_package(seeded_client, fmt="json"):
    """导出并返回 (包 dict, 原始文本)。scope=all。"""
    r = seeded_client.post("/api/export", json={"scope": "all", "format": fmt})
    assert r.status_code == 200, f"导出期望 200，实际 {r.status_code}：{r.text}"
    if fmt == "md":
        content = r.json().get("content")
        assert content, "md 导出期望返回 content 字符串"
        return None, content
    text = r.content.decode("utf-8")
    pkg = json.loads(text)
    return pkg, text


def _write_tmp_json(pkg):
    fd, path = tempfile.mkstemp(suffix=".json", prefix="matselect_import_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(pkg, f, ensure_ascii=False)
    return path


def _import_parse(seeded_client, path):
    with open(path, "rb") as f:
        r = seeded_client.post("/api/import/parse",
                                files={"file": ("pkg.json", f, "application/json")})
    return r


# ---------------------------------------------------------------------------
# 导出 + checksum 往返一致
# ---------------------------------------------------------------------------
def test_export_json_and_checksum_roundtrip(seeded_client):
    """P0 | E1/E2 checksum 往返一致：导出包 checksum == pack_checksum(materials)。"""
    pkg, _ = _export_package(seeded_client, fmt="json")
    assert "materials" in pkg and isinstance(pkg["materials"], list), \
        f"期望含 materials 数组，实际 keys={list(pkg)}"
    assert len(pkg["materials"]) >= 5, f"期望≥5条，实际 {len(pkg['materials'])}"
    assert "checksum" in pkg, f"期望含 checksum，实际 {list(pkg)}"
    expect = pack_checksum(pkg["materials"])
    assert pkg["checksum"] == expect, \
        f"checksum 不一致：包内={pkg['checksum']} 计算={expect}"


def test_export_md_returns_content(seeded_client):
    """P1 | E1 md 导出：返回 {content} 字符串且非空。"""
    _, content = _export_package(seeded_client, fmt="md")
    assert isinstance(content, str) and len(content) > 0, "md 内容应为非空字符串"


# ---------------------------------------------------------------------------
# 导入三段式 + 三种冲突策略
# ---------------------------------------------------------------------------
def test_import_skip_policy_no_change(seeded_client):
    """P0 | E2 冲突-skip：导入与本机相同 uid 的包 → 冲突被跳过，材料总数不变。"""
    before = seeded_client.get("/api/materials").json()["total"]
    pkg, _ = _export_package(seeded_client, fmt="json")
    path = _write_tmp_json(pkg)
    try:
        rp = _import_parse(seeded_client, path)
        assert rp.status_code == 200, f"parse 期望 200，实际 {rp.status_code}：{rp.text}"
        token = rp.json().get("token")
        assert token, f"期望返回 token，实际 {rp.json()}"
        rc = seeded_client.post("/api/import/commit",
                                 json={"token": token, "conflict_policy": "skip"})
        assert rc.status_code == 200, f"commit 期望 200，实际 {rc.status_code}：{rc.text}"
        after = seeded_client.get("/api/materials").json()["total"]
        assert after == before, f"skip 策略期望总数不变（{before}），实际 {after}"
    finally:
        os.remove(path)


def test_import_overwrite_policy_updates(seeded_client):
    """P0 | E2 冲突-overwrite：改同名材料的字段后用 overwrite → 该字段被覆盖更新。"""
    pkg, _ = _export_package(seeded_client, fmt="json")
    target = pkg["materials"][0]
    target_uid = target["uid"]
    target["price_max"] = 999  # 制造差异
    path = _write_tmp_json(pkg)
    try:
        token = _import_parse(seeded_client, path).json()["token"]
        rc = seeded_client.post("/api/import/commit",
                                 json={"token": token, "conflict_policy": "overwrite"})
        assert rc.status_code == 200, f"commit 期望 200，实际 {rc.status_code}：{rc.text}"
        d = seeded_client.get(f"/api/materials/{target_uid}").json()
        assert d["price_max"] == 999, \
            f"overwrite 期望 price_max=999，实际 {d.get('price_max')}"
    finally:
        os.remove(path)


def test_import_duplicate_policy_creates_new(seeded_client):
    """P0 | E2 冲突-duplicate：换 uid 导入 → 新增一条（总数+1）。"""
    before = seeded_client.get("/api/materials").json()["total"]
    pkg, _ = _export_package(seeded_client, fmt="json")
    pkg["materials"][0]["uid"] = "dup-" + uuid.uuid4().hex  # 换 uid → 视作新料
    path = _write_tmp_json(pkg)
    try:
        token = _import_parse(seeded_client, path).json()["token"]
        rc = seeded_client.post("/api/import/commit",
                                 json={"token": token, "conflict_policy": "duplicate"})
        assert rc.status_code == 200, f"commit 期望 200，实际 {rc.status_code}：{rc.text}"
        after = seeded_client.get("/api/materials").json()["total"]
        assert after == before + 1, f"duplicate 期望总数+1（{before}→{after}）"
    finally:
        os.remove(path)


# ---------------------------------------------------------------------------
# 校验失败：拒绝写库，不产生半截数据
# ---------------------------------------------------------------------------
def test_import_reject_bad_checksum_no_halfwrite(seeded_client):
    """P0 | E2 校验失败：篡改 checksum → parse 拒绝（IMPORT_REJECTED），材料总数不变。"""
    before = seeded_client.get("/api/materials").json()["total"]
    pkg, _ = _export_package(seeded_client, fmt="json")
    pkg["checksum"] = "sha256:" + "0" * 64  # 故意篡改
    path = _write_tmp_json(pkg)
    try:
        rp = _import_parse(seeded_client, path)
        assert rp.status_code in (400, 422), \
            f"期望校验失败 400/422，实际 {rp.status_code}：{rp.text}"
        if rp.status_code == 400:
            assert rp.json().get("error", {}).get("code") in ("IMPORT_REJECTED", "VALIDATION_ERROR"), \
                f"期望 IMPORT_REJECTED/VALIDATION_ERROR，实际 {rp.json()}"
        # 即使拿错误 token 去 commit 也应失败，且不产生半截数据
        rc = seeded_client.post("/api/import/commit",
                                 json={"token": "bad-token", "conflict_policy": "skip"})
        assert rc.status_code >= 400, f"坏 token commit 期望失败，实际 {rc.status_code}"
        after = seeded_client.get("/api/materials").json()["total"]
        assert after == before, f"校验失败后期望总数不变（{before}），实际 {after}（半截数据！）"
    finally:
        os.remove(path)


def test_import_reject_missing_required_field(seeded_client):
    """P0 | E2 必填缺失：材料缺 name → 解析阶段拒绝（不产生半截数据）。"""
    before = seeded_client.get("/api/materials").json()["total"]
    pkg, _ = _export_package(seeded_client, fmt="json")
    del pkg["materials"][0]["name"]  # 删除必填
    path = _write_tmp_json(pkg)
    try:
        rp = _import_parse(seeded_client, path)
        assert rp.status_code in (400, 422), \
            f"期望必填校验失败 400/422，实际 {rp.status_code}：{rp.text}"
        after = seeded_client.get("/api/materials").json()["total"]
        assert after == before, f"缺失必填后仍期望总数不变（{before}），实际 {after}"
    finally:
        os.remove(path)
