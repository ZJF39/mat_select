# -*- coding: utf-8 -*-
"""
check_seed.py —— 校验 data/*.json 是否符合建库契约。
仅依赖标准库与本地数据文件，不需要数据库，可在数据收集阶段独立跑通。
运行：python backend/scripts/check_seed.py
"""
import json
import os
import sys
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")

# 契约§4.6(a) 校验和算法
def pack_checksum(materials):
    canonical = json.dumps(materials, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# 参与完整率统计的字段（排除契约明确的可选字段 ul_yellow_card / iatf）
COMPLETENESS_FIELDS = [
    "name", "uid", "short_name", "category_path", "category_id", "grade_type", "aliases", "description",
    "density_min", "density_max",
    "tensile_strength_min", "tensile_strength_max",
    "elastic_modulus_min", "elastic_modulus_max",
    "elongation_min", "elongation_max",
    "notch_impact_min", "notch_impact_max",
    "hdt_min", "hdt_max",
    "service_temp_min", "service_temp_max", "service_temp_limit",
    "features", "cautions", "applications",
    "price_min", "price_max", "price_unit", "price_note", "molding_process",
    "cert_ul94", "cert_rohs", "cert_reach",
    "limitations", "source", "source_date", "value_type",
]

# min/max 数值字段对
RANGE_PAIRS = [
    ("density_min", "density_max"),
    ("tensile_strength_min", "tensile_strength_max"),
    ("elastic_modulus_min", "elastic_modulus_max"),
    ("elongation_min", "elongation_max"),
    ("notch_impact_min", "notch_impact_max"),
    ("hdt_min", "hdt_max"),
    ("service_temp_min", "service_temp_max"),
]


def is_filled(v):
    if v is None:
        return False
    if isinstance(v, (list, dict, str)) and len(v) == 0:
        return False
    return True


def cert_sub_value(mat, key):
    cert = mat.get("certifications")
    if not isinstance(cert, dict):
        return None
    return cert.get(key)


def main():
    report = []
    ok = True

    # 载入数据
    try:
        with open(os.path.join(DATA, "materials.json"), encoding="utf-8") as f:
            materials = json.load(f)["materials"]
    except Exception as e:
        report.append("❌ 无法读取 materials.json: %s" % e)
        _dump(report)
        return 1

    n = len(materials)
    report.append("① 材料条数 = %d （要求 == 50）" % n)
    if n == 50:
        report.append("   ✅ 通过")
    else:
        report.append("   ❌ 不通过")
        ok = False

    # ② 逐字段 min <= max
    range_errors = []
    for i, m in enumerate(materials):
        for lo, hi in RANGE_PAIRS:
            a, b = m.get(lo), m.get(hi)
            if a is None or b is None:
                continue
            if not (a <= b):
                range_errors.append("%s: %s(%s) > %s(%s)" % (m.get("name"), lo, a, hi, b))
    report.append("② 区间字段 min<=max 检查：%d 处错误" % len(range_errors))
    if not range_errors:
        report.append("   ✅ 通过")
    else:
        report.append("   ❌ 不通过")
        for e in range_errors[:20]:
            report.append("      - " + e)
        ok = False

    # ③ service_temp_limit == service_temp_max
    sl_errors = []
    for m in materials:
        if m.get("service_temp_limit") != m.get("service_temp_max"):
            sl_errors.append(m.get("name"))
    report.append("③ service_temp_limit == service_temp_max：%d 处错误" % len(sl_errors))
    if not sl_errors:
        report.append("   ✅ 通过")
    else:
        report.append("   ❌ 不通过")
        for e in sl_errors[:20]:
            report.append("      - " + e)
        ok = False

    # 附加：aliases>=2、cautions>=1、limitations>=1、applications>=2、certifications 含 ul94 或 rohs
    qual_errors = []
    for m in materials:
        if len(m.get("aliases") or []) < 2:
            qual_errors.append("%s: aliases<2" % m.get("name"))
        if len(m.get("cautions") or []) < 1:
            qual_errors.append("%s: cautions<1" % m.get("name"))
        if len(m.get("limitations") or []) < 1:
            qual_errors.append("%s: limitations<1" % m.get("name"))
        if len(m.get("applications") or []) < 2:
            qual_errors.append("%s: applications<2" % m.get("name"))
        cert = m.get("certifications") or {}
        if cert.get("ul94") is None and cert.get("rohs") is None:
            qual_errors.append("%s: cert 无 ul94/rohs" % m.get("name"))
        if m.get("value_type") != "typical":
            qual_errors.append("%s: value_type != typical" % m.get("name"))
    report.append("③b 内容质量（别名/注意/限制/应用/认证/value_type）：%d 处异常" % len(qual_errors))
    if not qual_errors:
        report.append("   ✅ 通过")
    else:
        report.append("   ❌ 不通过")
        for e in qual_errors[:20]:
            report.append("      - " + e)
        ok = False

    # ④ 必填字段非空率
    # 说明：契约允许「金属类 ul94 可为 null」，故 ul94 完整率仅统计非金属于材料；
    # 其余字段（除 ul_yellow_card/iatf 外）统计全量。通过判据为总体完整率 > 90%。
    report.append("④ 必填字段完整率（总体 >90% 即通过；ul94 对非金属统计）：")
    field_total = {k: 0 for k in COMPLETENESS_FIELDS}
    field_filled = {k: 0 for k in COMPLETENESS_FIELDS}
    for m in materials:
        is_metal = (m.get("category_path") or [None, None])[0] == "金属"
        for k in COMPLETENESS_FIELDS:
            # ul94 仅对非金属统计（金属按契约允许为 null）
            if k == "cert_ul94" and is_metal:
                continue
            field_total[k] += 1
            if k.startswith("cert_"):
                v = cert_sub_value(m, k.split("_", 1)[1])
            else:
                v = m.get(k)
            if is_filled(v):
                field_filled[k] += 1
    total_cells = sum(field_total.values())
    filled_cells = sum(field_filled.values())
    overall = filled_cells / total_cells * 100 if total_cells else 0
    low_fields = []
    for k in COMPLETENESS_FIELDS:
        if field_total[k] == 0:
            continue
        rate = field_filled[k] / field_total[k] * 100
        if rate < 90:
            low_fields.append((k, rate))
        report.append("   %-22s %5.1f%%  (%d/%d)" % (k, rate, field_filled[k], field_total[k]))
    report.append("   总体完整率 = %.2f%%" % overall)
    if overall > 90:
        report.append("   ✅ 通过（总体完整率 > 90%）")
    else:
        report.append("   ❌ 不通过")
        for k, r in low_fields:
            report.append("      - 字段 %s 完整率 %.1f%%" % (k, r))
        ok = False

    # ⑤ sample pack checksum 重算比对
    report.append("⑤ material_pack_sample.json 校验和重算比对：")
    try:
        with open(os.path.join(DATA, "material_pack_sample.json"), encoding="utf-8") as f:
            pack = json.load(f)
        stored = pack.get("checksum")
        recomputed = pack_checksum(pack.get("materials", []))
        report.append("   存储 checksum = %s" % stored)
        report.append("   重算 checksum = %s" % recomputed)
        if stored == recomputed:
            report.append("   ✅ 一致")
        else:
            report.append("   ❌ 不一致")
            ok = False
        mc = pack.get("material_count")
        if mc == len(pack.get("materials", [])):
            report.append("   ✅ material_count 与实际条目数一致(%d)" % mc)
        else:
            report.append("   ❌ material_count 不一致")
            ok = False
    except Exception as e:
        report.append("   ❌ 读取/校验失败: %s" % e)
        ok = False

    # term_alias 统计
    try:
        with open(os.path.join(DATA, "term_alias.json"), encoding="utf-8") as f:
            tal = json.load(f)["aliases"]
        types = {}
        for a in tal:
            types[a.get("type")] = types.get(a.get("type"), 0) + 1
        report.append("⑥ term_alias：共 %d 条，分布 %s （要求 ≥60）" % (len(tal), types))
        if len(tal) >= 60:
            report.append("   ✅ 通过")
        else:
            report.append("   ❌ 不通过")
            ok = False
    except Exception as e:
        report.append("   ❌ 读取失败: %s" % e)
        ok = False

    report.append("")
    report.append("==== 结论：%s ====" % ("✅ 全部通过" if ok else "❌ 存在不通过项"))
    _dump(report)
    return 0 if ok else 1


def _dump(report):
    text = "\n".join(report) + "\n"
    out = os.path.join(DATA, "_check_seed_report.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    # 同时尝试输出到 stdout（若环境回传）
    try:
        sys.stdout.write(text)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
