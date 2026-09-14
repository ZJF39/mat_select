# -*- coding: utf-8 -*-
"""配置仓储（契约 §4.6(b) `settings_kv` / `app_meta`，§4.4 设置与系统接口）。

读写范围：
- `weights`：推荐五维权重（**百分制**，与 init_db._seed_settings 写入的口径一致）
- `feedback_penalty`：`{"threshold": 2, "max": 15}`
- `app_meta`：版本号 / 最后备份时间
"""
from __future__ import annotations

from app.core.config import (
    DEFAULT_PENALTY,
    DEFAULT_WEIGHTS,
    PENALTY_DIM_WEIGHTS,
    PENALTY_KEY,
    WEIGHTS_KEY,
)
from app.db.connection import json_dumps, json_loads, now_iso
from app.repository.base import execute, query_one


# ---------------- settings_kv ----------------
def get_kv(key: str, default=None):
    row = query_one("SELECT value FROM settings_kv WHERE key=?", (key,))
    if row is None:
        return default
    return json_loads(row["value"])


def set_kv(key: str, value) -> None:
    execute(
        "INSERT INTO settings_kv(key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, json_dumps(value), now_iso()),
    )


# ---------------- 权重 ----------------
def default_weights_percent() -> dict:
    """默认权重（百分制，合计 100）。"""
    total = sum(DEFAULT_WEIGHTS.values()) or 1.0
    return {k: round(v / total * 100, 2) for k, v in DEFAULT_WEIGHTS.items()}


def get_weights_percent() -> dict:
    """读取百分制权重；缺失/损坏时回退默认值。"""
    raw = get_kv(WEIGHTS_KEY, None)
    if not isinstance(raw, dict) or not raw:
        return default_weights_percent()
    out = {}
    for k in DEFAULT_WEIGHTS.keys():
        try:
            out[k] = float(raw.get(k, DEFAULT_WEIGHTS[k] * 100))
        except (TypeError, ValueError):
            out[k] = DEFAULT_WEIGHTS[k] * 100
    return out


def set_weights_percent(weights: dict) -> None:
    set_kv(WEIGHTS_KEY, {k: round(float(v), 4) for k, v in weights.items()})


def get_weights_fraction() -> dict:
    """归一化到 Σ=1 的分数权重，供打分使用。"""
    percent = get_weights_percent()
    total = sum(percent.values()) or 1.0
    return {k: v / total for k, v in percent.items()}


# ---------------- 降权阈值 ----------------
def get_penalty() -> dict:
    raw = get_kv(PENALTY_KEY, None)
    if not isinstance(raw, dict):
        return dict(DEFAULT_PENALTY)
    return {
        "threshold": int(raw.get("threshold", DEFAULT_PENALTY["threshold"])),
        "max": int(raw.get("max", DEFAULT_PENALTY["max"])),
    }


def set_penalty(cfg: dict) -> None:
    set_kv(
        PENALTY_KEY,
        {
            "threshold": int(cfg.get("threshold", DEFAULT_PENALTY["threshold"])),
            "max": int(cfg.get("max", DEFAULT_PENALTY["max"])),
        },
    )


def get_penalty_dim_weights() -> dict:
    """各反馈维度降权权重；优先读 app_meta，缺失回退 config 常量。"""
    raw = get_meta_json("penalty_dim_weights")
    if isinstance(raw, dict) and raw:
        return {str(k): float(v) for k, v in raw.items()}
    return dict(PENALTY_DIM_WEIGHTS)


# ---------------- app_meta ----------------
def get_meta(key: str, default=None):
    """读取 app_meta 原始字符串值（如 version / last_backup_at）。"""
    row = query_one("SELECT value FROM app_meta WHERE key=?", (key,))
    if row is None:
        return default
    return row["value"]


def get_meta_json(key: str, default=None):
    """读取 app_meta 中的 JSON 值（如 penalty_dim_weights）。"""
    row = query_one("SELECT value FROM app_meta WHERE key=?", (key,))
    if row is None:
        return default
    return json_loads(row["value"])


def set_meta(key: str, value) -> None:
    execute(
        "INSERT INTO app_meta(key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
