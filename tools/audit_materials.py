#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""材料库数据审计（tools/audit_materials.py）。

用途：
    遍历 data/materials.json（种子权威源），逐条校验字段完整性、格式规范与内容正确性，
    输出异常清单；`--fix` 应用可自动修正项（先备份原文件）。
    `--db` 指定 SQLite 库时，额外核对库内数据与种子是否一致（按 uid）。

规则分层：
    [ERR ] 结构/枚举/数值区间错误 —— 必须修（多数可 --fix 自动修）
    [WARN] 跨字段逻辑可疑（如增强级伸长率过大、上限低于区间上界）—— 人工判断
    [INFO] 冗余 / 口径提示（别名与名称重复、描述过短等）

用法：
    & "<venv python>" tools\\audit_materials.py [--fix] [--db data\\matselect.db]
"""
from __future__ import annotations

import io
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MATERIALS_JSON = DATA / "materials.json"
CATEGORIES_JSON = DATA / "categories.json"

# ---------------------------------------------------------------- 基准定义

FIELDS = {
    "name": str, "uid": str, "short_name": str, "category_path": list,
    "category_id": int, "grade_type": str, "aliases": list, "description": str,
    "density_min": (int, float), "density_max": (int, float),
    "tensile_strength_min": (int, float), "tensile_strength_max": (int, float),
    "elastic_modulus_min": (int, float), "elastic_modulus_max": (int, float),
    "elongation_min": (int, float), "elongation_max": (int, float),
    "notch_impact_min": (int, float), "notch_impact_max": (int, float),
    "hdt_min": (int, float), "hdt_max": (int, float),
    "service_temp_min": (int, float), "service_temp_max": (int, float),
    "service_temp_limit": (int, float),
    "features": list, "cautions": list, "applications": list,
    "price_min": (int, float), "price_max": (int, float), "price_unit": str,
    "price_note": str, "molding_process": list, "certifications": dict,
    "limitations": list, "source": str, "source_date": str, "value_type": str,
}
RANGE_PAIRS = [
    ("density", "g/cm³"), ("tensile_strength", "MPa"), ("elastic_modulus", "GPa"),
    ("elongation", "%"), ("notch_impact", "kJ/m²"), ("hdt", "°C"),
    ("service_temp", "°C"), ("price", "元/kg"),
]
# 物理合理域（默认域；按二级分类用 DOMAIN_BOUNDS 覆盖）：
# - 橡胶/热塑弹性体的模量可低至 0.001 GPa；金属冲击韧性以 kJ/m² 计可达数百；
# - 热塑性塑料断裂伸长率上限放宽到 1200%（HDPE 实测可达 1000%）。
DOMAIN_BOUNDS = {
    "橡胶": {"elastic_modulus": (0.0005, 450.0)},
    "热塑性弹性体": {"elastic_modulus": (0.0005, 450.0)},
    "钢材": {"notch_impact": (1.0, 900.0)},
    "铝合金": {"notch_impact": (1.0, 900.0)},
    "铜合金": {"notch_impact": (1.0, 900.0)},
    "锌合金": {"notch_impact": (1.0, 900.0)},
    "镁合金": {"notch_impact": (1.0, 900.0)},
    # 发泡类（硬质聚氨酯泡沫等）密度/强度远低于密实材料
    "通用热固性": {"density": (0.03, 20.0), "tensile_strength": (0.1, 2500.0),
                  "elastic_modulus": (0.0005, 450.0)},
}
PLAUSIBLE = {
    "density": (0.5, 20.0), "tensile_strength": (1.0, 2500.0),
    "elastic_modulus": (0.005, 450.0), "elongation": (0.1, 1200.0),
    "notch_impact": (0.5, 150.0), "hdt": (-60.0, 450.0),
    # 氟塑料（PTFE/PFA/FEP）长期使用下限可至 -200°C
    "service_temp": (-200.0, 400.0),
}
CERT_KEYS = {"ul94", "ul_yellow_card", "rohs", "reach", "iatf"}
UL94_LEVELS = {"HB", "V-2", "V-1", "V-0", "5VA", "5VB", "HBF"}
VALUE_TYPES = {"typical", "guaranteed"}
PROC_CANON = {"注塑", "挤出", "吹塑", "压铸", "冲压", "机加工", "模压", "浇注", "缠绕", "烧结", "拉挤"}
# 「挤出」的非规范同义词（term_alias 中登记为挤出同义词的写法）
PROC_ALIAS_FIX = {"挤压": "挤出", "挤塑": "挤出", "注射成型": "注塑", "射出成型": "注塑"}
# 叶分类 → 唯一 grade_type
LEAF_GRADE_TYPE = {
    "通用塑料": "通用塑料", "工程塑料": "工程塑料", "特种工程塑料": "特种工程塑料",
    "通用热固性": "热固性塑料", "增强塑料": "热固性塑料",
    "钢材": "金属材料", "铝合金": "金属材料", "铜合金": "金属材料", "锌合金": "金属材料",
    "镁合金": "金属材料",
    "热塑性弹性体": "弹性体", "橡胶": "弹性体", "增强复合材料": "复合材料",
}
UID_RE = re.compile(r"^[0-9a-f]{32}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_categories_leaves() -> dict[str, tuple[str, ...]]:
    data = json.loads(CATEGORIES_JSON.read_text(encoding="utf-8")) if False else json.loads(
        (DATA / "categories.json").read_text(encoding="utf-8"))
    leaves: dict[str, tuple[str, ...]] = {}
    for root in data["categories"]:
        for child in root.get("children", []):
            leaves[child["name"]] = (root["name"], child["name"])
    return leaves


def audit(mats: list, leaves: dict) -> tuple[list, list, list]:
    """返回 (errors, warns, infos)。每条 = dict(rule, name, uid, detail, fix)。"""
    errors: list = []
    warns: list = []
    infos: list = []

    def add(bucket, rule, m, detail, fix=None):
        bucket.append({"rule": rule, "name": m.get("name", "?"), "uid": m.get("uid", "-"),
                       "detail": detail, "fix": fix})

    seen_name: dict[str, str] = {}
    seen_uid: dict[str, str] = {}

    for m in mats:
        name = m.get("name", "?")
        # E1 字段完整性 / 类型
        for key, typ in FIELDS.items():
            if key not in m:
                add(errors, "E1-缺失字段", m, f"缺少字段 {key}")
            elif m[key] is not None and not isinstance(m[key], typ):
                add(errors, "E1-类型", m, f"{key} 类型应为 {typ}，实际 {type(m[key]).__name__}")
        # E2 uid
        uid = str(m.get("uid", ""))
        if not UID_RE.match(uid):
            add(errors, "E2-uid格式", m, f"uid 非 32 位小写十六进制：{uid!r}")
        if uid in seen_uid:
            add(errors, "E3-uid重复", m, f"与「{seen_uid[uid]}」重复")
        else:
            seen_uid[uid] = name
        if name in seen_name:
            add(errors, "E4-名称重复", m, f"与「{seen_name[name]}」重名")
        else:
            seen_name[name] = name
        # E5 分类
        path = m.get("category_path") or []
        if len(path) != 2 or path[0] not in {r for v in leaves.values() for r in (v[0],)}:
            add(errors, "E5-分类路径", m, f"category_path 应为 [大类, 二级] 两级：{path}")
        elif path[-1] not in leaves:
            add(errors, "E5-分类路径", m, f"二级分类「{path[-1]}」不在分类骨架中")
        else:
            want = leaves[path[-1]]
            if tuple(path) != want:
                add(errors, "E5-分类路径不一致", m, f"path={path} 与骨架 {want} 不符")
        # E6 grade_type 与分类一致性
        expect_gt = LEAF_GRADE_TYPE.get(str(path[-1] if len(path) == 2 else ""))
        if expect_gt and m.get("grade_type") != expect_gt:
            add(errors, "E6-grade_type不一致", m,
                f"grade_type={m.get('grade_type')!r}，应为 {expect_gt!r}",
                fix=("set_grade_type", expect_gt))
        # E7 数值区间 min<=max
        for base, _unit in RANGE_PAIRS:
            lo, hi = m.get(f"{base}_min"), m.get(f"{base}_max")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
                add(errors, "E7-区间颠倒", m, f"{base}: min {lo} > max {hi}",
                    fix=("swap_range", base))
        # E8 物理合理域（按二级分类取覆盖域）
        bounds = dict(PLAUSIBLE)
        if len(path) == 2:
            bounds.update(DOMAIN_BOUNDS.get(path[-1], {}))
        for base, (lo, hi) in bounds.items():
            for side in ("min", "max"):
                v = m.get(f"{base}_{side}")
                if isinstance(v, (int, float)) and not (lo <= v <= hi):
                    add(errors, "E8-数值越界", m,
                        f"{base}_{side}={v} 超出合理域 [{lo},{hi}]")
        # E9 工艺口径
        procs = m.get("molding_process") or []
        for i, p in enumerate(procs):
            if not isinstance(p, str) or not p.strip():
                add(errors, "E9-工艺空值", m, "molding_process 含空元素", fix=("del_proc", i))
            elif p != "挤压" and p not in PROC_CANON:
                add(errors, "E9-工艺非标准词", m, f"工艺「{p}」不在标准集合 {sorted(PROC_CANON)}")
            elif p == "挤压":
                add(errors, "E9-工艺非标准词", m, "工艺「挤压」应为「挤出」",
                    fix=("set_proc", i, "挤出"))
        # E10 认证结构
        cert = m.get("certifications")
        if isinstance(cert, dict):
            missing = CERT_KEYS - set(cert)
            if missing:
                add(errors, "E10-认证字段缺失", m, f"缺 {sorted(missing)}",
                    fix=("fill_cert", {k: None for k in missing}))
            ul = cert.get("ul94")
            if ul is not None and str(ul).upper() not in UL94_LEVELS:
                add(errors, "E10-UL94级别非法", m, f"ul94={ul!r} 不在 {sorted(UL94_LEVELS)}")
            for k in ("rohs", "reach"):
                if k in cert and not isinstance(cert[k], bool):
                    add(errors, "E10-认证布尔型", m, f"certifications.{k} 应为布尔，实际 {cert[k]!r}")
        else:
            add(errors, "E10-认证结构", m, f"certifications 应为对象，实际 {type(cert).__name__}")
        # E11 枚举
        if m.get("value_type") not in VALUE_TYPES:
            add(errors, "E11-value_type非法", m, f"value_type={m.get('value_type')!r}",
                fix=("set_value_type", "typical"))
        if m.get("price_unit") != "元/kg":
            add(errors, "E12-价格单位", m, f"price_unit={m.get('price_unit')!r} 应为 元/kg",
                fix=("set_price_unit", "元/kg"))
        sd = str(m.get("source_date", ""))
        if not DATE_RE.match(sd):
            add(errors, "E13-日期格式", m, f"source_date={sd!r} 应为 YYYY-MM-DD")
        # W 跨字段逻辑
        smin, smax = m.get("service_temp_min"), m.get("service_temp_max")
        limit = m.get("service_temp_limit")
        if isinstance(smax, (int, float)) and isinstance(limit, (int, float)) and limit < smax:
            add(warns, "W1-上限低于区间上界", m, f"长期使用温度上限 {limit} < 使用温度上限 {smax}")
        if (m.get("elongation_max") or 0) > 25 and _reinforced(m):
            add(warns, "W2-增强级伸长率过大", m,
                f"纤维增强材料 elongation_max={m.get('elongation_max')}%（玻纤级通常 <6%）")
        if not str(m.get("description", "")).strip():
            add(warns, "W3-描述为空", m, "description 为空")
        elif len(str(m.get("description"))) < 12:
            add(infos, "I1-描述过短", m, f"description 仅 {len(str(m.get('description')))} 字")
        for arr, label in (("aliases", "别名"), ("features", "特性"), ("applications", "应用")):
            arrv = m.get(arr)
            if not isinstance(arrv, list) or not arrv:
                add(warns, "W4-数组为空", m, f"{label}({arr}) 为空")
        # I2 别名与名称重复
        for a in m.get("aliases") or []:
            if a == name:
                add(infos, "I2-别名重复名称", m, f"别名「{a}」与名称相同")
    return errors, warns, infos


def _reinforced(m: dict) -> bool:
    text = " ".join(str(x) for x in (
        m.get("name"), m.get("short_name"), m.get("description"), *(m.get("aliases") or []),
    ) if x)
    # 例外体系：PTFE 填强配方、EPDM/橡胶增韧体系即便含填充仍保持高伸长率（数据正确）
    if re.search(r"ptfe|epdm|增韧|保险杠料", text, re.I):
        return False
    return bool(re.search(r"玻纤|玻璃纤维|碳纤|碳纤维|gf\s*\d+|cf\s*\d+|玻璃珠|gb\s*\d+|矿物|滑石", text, re.I))


def apply_fixes(mats: list, errors: list) -> tuple[int, list]:
    """把 fix 标记写回数据。返回 (修正条数, 未应用的 fix)。"""
    by_uid: dict[str, dict] = {}
    for m in mats:
        by_uid.setdefault(str(m.get("uid")), m)
    applied, skipped = 0, []
    for e in errors:
        fix = e.get("fix")
        if not fix:
            continue
        m = by_uid.get(str(e["uid"]))
        if m is None:
            skipped.append({**e, "reason": "uid 未找到"})
            continue
        try:
            if fix[0] == "set_grade_type":
                m["grade_type"] = fix[1]
            elif fix[0] == "swap_range":
                base = fix[1]
                m[f"{base}_min"], m[f"{base}_max"] = m[f"{base}_max"], m[f"{base}_min"]
            elif fix[0] == "set_proc":
                m["molding_process"][fix[1]] = fix[2]
            elif fix[0] == "del_proc":
                del m["molding_process"][fix[1]]
            elif fix[0] == "fill_cert":
                for k, v in fix[1].items():
                    m["certifications"].setdefault(k, v)
            elif fix[0] == "set_value_type":
                m["value_type"] = fix[1]
            elif fix[0] == "set_price_unit":
                m["price_unit"] = fix[1]
            else:
                raise ValueError(f"未知 fix {fix}")
            applied += 1
        except Exception as exc:  # noqa: BLE001
            skipped.append({**e, "reason": repr(exc)})
    return applied, skipped


def check_db(seed: list, db_path: Path) -> dict:
    """核对库内数据与种子一致性（uid 级）。"""
    import sqlite3
    if not db_path.exists():
        return {"error": f"库不存在：{db_path}"}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT uid, name, archived, molding_process, grade_type FROM material").fetchall()
    db_map = {r["uid"]: dict(r) for r in rows}
    # 种子可能整体换过 uid（发版重生成），uid 联接会误报「库内独有/种子独有」；
    # 名称经审计保证唯一，故以名称为联接键核对内容，uid 仅做差异提示。
    seed_map = {m["name"]: m for m in seed}
    db_by_name = {r["name"]: dict(r) for r in rows}
    uid_diff = []
    for name, m in seed_map.items():
        r = db_by_name.get(name)
        if r is not None and r["uid"] != m["uid"]:
            uid_diff.append(f"{name}: 库 uid={r['uid'][:8]} 种子 uid={m['uid'][:8]}")
    only_db = [r["name"] for r in db_map.values() if r["name"] not in seed_map]
    only_seed = [name for name in seed_map if name not in db_by_name]
    mismatch = []
    for name, m in seed_map.items():
        r = db_by_name.get(name)
        if r is None:
            continue
        dbp = json.loads(r["molding_process"] or "[]")
        diff = []
        if dbp != m["molding_process"]:
            diff.append(f"molding_process 库={dbp} 种子={m['molding_process']}")
        if r["grade_type"] != m["grade_type"]:
            diff.append(f"grade_type 库={r['grade_type']}")
        if diff:
            mismatch.append(f"{name}: " + "；".join(diff))
    return {
        "db_count": len(rows), "seed_count": len(seed),
        "db_only": only_db, "seed_only": only_seed,
        "uid_diff": uid_diff, "field_diff": mismatch,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="应用可自动修正项（先备份）")
    ap.add_argument("--db", default="", help="SQLite 库路径（可选，做一致性核对）")
    args = ap.parse_args()

    seed = json.loads(MATERIALS_JSON.read_text(encoding="utf-8"))["materials"]
    leaves = load_categories_leaves()
    errors, warns, infos = audit(seed, leaves)

    print(f"===== 材料库审计 · {len(seed)} 条 =====")
    for label, bucket in (("错误", errors), ("警告", warns), ("提示", infos)):
        print(f"\n---- {label} {len(bucket)} 条 ----")
        for e in bucket:
            print(f"[{e['rule']}] {e['name']} · {e['detail']}")

    fixed = 0
    if args.fix:
        fixable = [e for e in errors if e.get("fix")]
        backup = MATERIALS_JSON.with_suffix(".json.bak")
        shutil.copy2(MATERIALS_JSON, backup)
        fixed, skipped = apply_fixes(seed, errors)
        MATERIALS_JSON.write_text(
            json.dumps({"materials": seed}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        print(f"\n[fix] 已应用 {fixed} 项修正（备份：{backup}）")
        if skipped:
            print(f"[fix] 未应用 {len(skipped)} 项：")
            for s in skipped:
                print(f"  - {s['name']} · {s['reason']}")

    if args.db:
        rep = check_db(seed, Path(args.db))
        print("\n---- 库内一致性 ----")
        for k, v in rep.items():
            if isinstance(v, list):
                print(f"{k}: {len(v)} 条")
                for x in v[:20]:
                    print(f"  - {x}")
            else:
                print(f"{k}: {v}")

    print(f"\n===== 汇总：错误 {len(errors)} / 警告 {len(warns)} / 提示 {len(infos)}，已修正 {fixed} =====")


if __name__ == "__main__":
    main()
