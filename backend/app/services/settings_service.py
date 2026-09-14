# -*- coding: utf-8 -*-
"""设置 / 系统服务：推荐权重、反馈降权阈值、操作日志、数据备份（契约 §4.4）。

权重口径：`settings_kv.weights` 存**百分制**（Δ 归一化后 Σ=100），
`get_weights_fraction()` 再归一化到 Σ=1 供打分使用，与 `init_db._seed_settings` 一致。
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import APP_VERSION, DATA_DIR
from app.core.errors import validation_error
from app.core.logging import write_log
from app.repository.settings_repo import (
    default_weights_percent,
    get_meta,
    get_penalty,
    get_weights_percent,
    set_meta,
    set_penalty,
    set_weights_percent,
)
from app.repository.log_repo import list_logs as _list_logs
from app.core.config import WEIGHT_HINTS, WEIGHT_LABELS

_TZ = timezone(timedelta(hours=8))
BACKUP_DIR = Path(DATA_DIR) / "backups"


def _label(key: str) -> str:
    return WEIGHT_LABELS.get(key, key)


def _hint(key: str) -> str:
    return WEIGHT_HINTS.get(key, "")


def get_weights() -> dict:
    """契约 §4.4：{dims:[{key,label,weight,hint}], penalty:{threshold,max}, sum}"""
    percent = get_weights_percent()
    dims = [
        {"key": k, "label": _label(k), "weight": round(float(v), 2), "hint": _hint(k)}
        for k, v in percent.items()
    ]
    return {"dims": dims, "penalty": get_penalty(), "sum": round(sum(percent.values()), 2)}


def save_weights(dims, penalty=None) -> dict:
    """保存权重：自动归一化到 Σ=100（原型 02 §10）。"""
    current = get_weights_percent()
    if dims:
        incoming = {}
        for d in dims:
            key = d.get("key") if isinstance(d, dict) else None
            if key not in current:
                raise validation_error(f"未知的权重维度：{key}")
            try:
                w = float(d.get("weight"))
            except (TypeError, ValueError):
                raise validation_error(f"权重值非法：{key}")
            if w < 0:
                raise validation_error(f"权重不能为负：{key}")
            incoming[key] = w
        for k in current:
            incoming.setdefault(k, current[k])
        total = sum(incoming.values())
        if total <= 0:
            raise validation_error("权重合计必须大于 0")
        normalized = {k: round(v / total * 100.0, 4) for k, v in incoming.items()}
        set_weights_percent(normalized)
    if penalty:
        set_penalty(penalty)
    write_log("保存推荐配置")
    return get_weights()


def list_logs(limit: int = 50) -> list[dict]:
    return _list_logs(int(limit))


def backup_status() -> dict:
    last = get_meta("last_backup_at", None)
    return {"last_backup_at": last, "location": str(BACKUP_DIR)}


def run_backup() -> dict:
    """把 SQLite 单文件复制到 data/backups/matselect_YYYYMMDD_HHMMSS.db（PRD §6 数据安全）。"""
    from app.core.config import DB_PATH

    src = Path(DB_PATH)
    if not src.exists():
        raise validation_error("数据库文件不存在，无法备份")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(_TZ).strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"matselect_{stamp}.db"
    shutil.copy2(src, dst)
    ts = datetime.now(_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    set_meta("last_backup_at", ts)
    write_log("数据备份", dst.name)
    return {"ok": True, "last_backup_at": ts, "location": str(dst)}


def health(material_count: int) -> dict:
    return {"ok": True, "version": APP_VERSION, "materials": material_count}
