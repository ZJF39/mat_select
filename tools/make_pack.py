#!/usr/bin/env python
"""把大模型生成的材料 JSON 转成**可直接导入 MatSelect 的材料包**。

为什么需要它：
- 应用侧的导入接口会校验 `checksum`（契约 §4.6(a)：对 materials 数组做 canonical JSON 后取 sha256）。
  大模型无法可靠计算 sha256，自行编造的校验和会导致**导入被拒绝**。
- 本工具用与后端**完全相同**的算法计算校验和（直接复用 `app.services.io_service.pack_checksum`），
  并在生成前做一次机器校验（字段/分类/工艺/区间/硬约束一致性）。

用法：
    python tools/make_pack.py <输入.json> [-o 输出.json] [--check] [--allow-warn]

输入容错：
- 裸数组 `[ {...}, {...} ]`
- `{"materials": [ ... ]}`
- 完整包 `{"pack_version":1, ..., "materials":[...]}`
- **带 Markdown 代码块的文件**（自动从 ```json ... ``` 中抽取）

退出码：0 = 通过（可导入）；1 = 存在 ERROR（拒绝生成）；2 = 文件/解析问题
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ---------------------------------------------------------------------------
# 规范字典（与 docs/prompts/01-生成新材料.md 保持一致；改动请同步）
# ---------------------------------------------------------------------------
CATEGORY_TREE = {
    "热塑性塑料": ["通用塑料", "工程塑料", "特种工程塑料"],
    "热固性塑料": ["通用热固性", "增强塑料"],
    "金属": ["钢材", "铝合金", "铜合金", "锌合金"],
    "弹性体": ["热塑性弹性体", "橡胶"],
    "复合材料": ["增强复合材料"],
}
GRADE_TYPES = {"通用塑料", "工程塑料", "特种工程塑料", "热固性塑料", "弹性体", "金属材料", "复合材料"}
PROCESSES = {"注塑", "挤出", "模压", "浇注", "冲压", "机加工", "压铸", "吹塑", "挤压", "缠绕"}
FEATURES = {
    "阻燃", "耐热", "耐高温", "超耐热", "耐化学", "耐油", "耐候", "耐水解", "绝缘", "电性好",
    "导电", "导热好", "高强度", "高刚性", "韧性好", "高冲击", "耐磨", "自润滑", "耐疲劳",
    "尺寸稳定", "低翘曲", "低吸湿", "高流动", "透明", "软触感", "轻量", "低成本", "易成型",
    "可焊", "耐回流焊",
}
PART_SYNONYMS = {
    "接插件": "连接器", "端子台": "连接器", "connector": "连接器", "插接件": "连接器",
    "熔断器底座": "保险丝座", "保险丝盒": "保险丝座", "fuse holder": "保险丝座",
    "控制器外壳": "ECU壳体", "电控单元壳体": "ECU壳体", "ECU housing": "ECU壳体",
    "传感器固定座": "传感器支架", "sensor bracket": "传感器支架",
    "继电器骨架": "继电器底座", "继电器座": "继电器底座",
    "卡子": "卡扣", "clip": "卡扣", "固定卡": "卡扣",
    "空调出风口": "出风口", "风道": "出风口", "风口": "出风口",
    "电子外壳": "外壳", "小壳体": "外壳", "电气外壳": "外壳",
    "结构支架": "支架", "支座": "支架",
    "内饰件": "装饰件", "美观件": "装饰件",
    "冲压件": "钣金件",
    "螺丝件": "紧固件", "螺栓件": "紧固件",
    "散热器": "散热件",
    "绝缘子": "绝缘件",
}
FEATURE_SYNONYMS = {
    "高耐热": "耐热", "耐热好": "耐热", "耐热中": "耐热", "耐热性佳": "耐热",
    "超高耐热": "超耐热", "耐化学性好": "耐化学", "耐化学性": "耐化学", "耐化学中": "耐化学",
    "电绝缘": "绝缘", "强度高": "高强度", "刚性好": "高刚性", "刚度高": "高刚性",
    "超高刚性": "高刚性", "成本低": "低成本", "价廉": "低成本", "尺寸好": "尺寸稳定",
    "低吸水": "低吸湿", "吸湿小": "低吸湿", "成型快": "易成型", "易加工": "易成型",
    "量产好": "易成型", "密度小": "轻量", "耐候性好": "耐候", "阻燃性好": "阻燃",
}
# 区间字段（成对出现，需 min ≤ max）
RANGE_KEYS = ("density", "tensile_strength", "elastic_modulus", "elongation",
              "notch_impact", "hdt", "price")
ARRAY_KEYS = ("aliases", "features", "applications", "molding_process", "limitations")
ARRAY_COLS = {"aliases", "features", "applications", "limitations"}   # 影响 FTS 的数组列

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# ---------------------------------------------------------------------------
# 输入解析
# ---------------------------------------------------------------------------
def load_input(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    # 容错：用户可能整段粘了带 ```json 围栏的输出
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 不是合法 JSON：{exc}")
        raise SystemExit(2)

    if isinstance(data, list):
        mats = data
    elif isinstance(data, dict):
        mats = data.get("materials")
        if data.get("pack_version") not in (None, 1):
            warn(f"忽略输入中的 pack_version={data.get('pack_version')}，输出统一为 1")
    else:
        print("[ERROR] 顶层既不是数组也不是对象")
        raise SystemExit(2)

    if not isinstance(mats, list) or not mats:
        print("[ERROR] 未找到 materials 数组，或数组为空")
        raise SystemExit(2)
    return mats


def _clean_scalar(v):
    """空字符串统一视为「无数据」（契约 §3.1：禁止用空串表示空值）。"""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


# ---------------------------------------------------------------------------
# 规整 + 校验
# ---------------------------------------------------------------------------
def normalize_one(i: int, m) -> dict | None:
    tag = f"第 {i + 1} 条"
    if not isinstance(m, dict):
        err(f"{tag}：不是对象，无法处理")
        return None

    out = {k: _clean_scalar(v) for k, v in m.items()}
    name = (out.get("name") or "").strip() if isinstance(out.get("name"), str) else out.get("name")
    if not name:
        err(f"{tag}：缺少必填字段 name（导入会被后端拒绝）")
        return None
    out["name"] = name
    tag = f"「{name}」"

    # uid / 默认值 / 删掉不该出现的字段
    if not out.get("uid"):
        out["uid"] = uuid.uuid4().hex
    else:
        u = str(out["uid"]).strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", u):
            warn(f"{tag}：uid 不是 32 位十六进制，已重新生成")
            u = uuid.uuid4().hex
        out["uid"] = u.lower()
    if out.pop("checksum", None) is not None:
        warn(f"{tag}：删除了自带的 checksum 字段（校验和由本工具计算）")
    for k in ("id", "created_at", "updated_at", "archived"):
        out.pop(k, None)
    out.setdefault("value_type", "typical")
    if out.get("value_type") != "typical":
        warn(f"{tag}：value_type={out.get('value_type')}（本库默认且推荐用 typical）")
    if not out.get("price_unit") and out.get("price_min") is not None:
        out["price_unit"] = "元/kg"
    if out.get("price_unit") and out["price_unit"] != "元/kg":
        warn(f"{tag}：price_unit={out['price_unit']}（本库约定 元/kg）")

    # 分类
    path = out.get("category_path")
    if isinstance(path, str):
        path = [p.strip() for p in re.split(r"[/>、,]", path) if p.strip()]
        out["category_path"] = path
    if not isinstance(path, list) or len(path) != 2:
        err(f"{tag}：category_path 必须是 2 元素数组，如 [\"热塑性塑料\",\"工程塑料\"]；实际={path!r}")
    else:
        big, sub = str(path[0]).strip(), str(path[1]).strip()
        if big not in CATEGORY_TREE:
            err(f"{tag}：分类大类「{big}」不在字典内（可选：{'/'.join(CATEGORY_TREE)}）")
        elif sub not in CATEGORY_TREE[big]:
            err(f"{tag}：分类子类「{sub}」不属于「{big}」（可选：{'/'.join(CATEGORY_TREE[big])}）")
        out["category_path"] = [big, sub]
    if out.get("grade_type") and out["grade_type"] not in GRADE_TYPES:
        warn(f"{tag}：grade_type「{out['grade_type']}」不在字典内，建议用 {'/'.join(sorted(GRADE_TYPES))}")

    # 工艺
    procs = out.get("molding_process")
    if isinstance(procs, str):
        procs = [p.strip() for p in re.split(r"[/、,]", procs) if p.strip()]
    if not isinstance(procs, list) or not procs:
        err(f"{tag}：molding_process 至少要有 1 个工艺")
    else:
        fixed = []
        for p in procs:
            p = str(p).strip()
            if p in PROCESSES:
                fixed.append(p)
            else:
                mapped = PROC_SYNONYMS.get(p)
                if mapped:
                    fixed.append(mapped)
                    warn(f"{tag}：工艺「{p}」→「{mapped}」（字典规范词）")
                else:
                    err(f"{tag}：工艺「{p}」不在字典内（可选：{'/'.join(sorted(PROCESSES))}）")
        out["molding_process"] = list(dict.fromkeys(fixed))

    # 特性
    feats = out.get("features")
    if isinstance(feats, str):
        feats = [x.strip() for x in re.split(r"[/、,]", feats) if x.strip()]
    if not isinstance(feats, list) or len(feats) < 2:
        warn(f"{tag}：features 建议 2~6 个（当前 {len(feats) if isinstance(feats, list) else 0} 个）")
    if isinstance(feats, list):
        fixed = []
        for f in feats:
            f = str(f).strip()
            if f in FEATURES:
                fixed.append(f)
            elif f in FEATURE_SYNONYMS:
                fixed.append(FEATURE_SYNONYMS[f])
                warn(f"{tag}：特性「{f}」→「{FEATURE_SYNONYMS[f]}」（同义归并）")
            else:
                fixed.append(f)
                warn(f"{tag}：特性「{f}」不在规范词表内——建议改用规范词，否则同义检索会漏")
        out["features"] = list(dict.fromkeys(fixed))

    # 应用场景
    apps = out.get("applications")
    if isinstance(apps, str):
        apps = [x.strip() for x in re.split(r"[/、,]", apps) if x.strip()]
    if not isinstance(apps, list) or len(apps) < 2:
        warn(f"{tag}：applications 建议 ≥2 个（当前 {len(apps) if isinstance(apps, list) else 0} 个）")
    if isinstance(apps, list):
        fixed = []
        for a in apps:
            a = str(a).strip()
            mapped = PART_SYNONYMS.get(a)
            if mapped:
                fixed.append(mapped)
                warn(f"{tag}：应用场景「{a}」→「{mapped}」（零件标准词，避免推荐术语匹配漏）")
            else:
                fixed.append(a)
        out["applications"] = list(dict.fromkeys(fixed))

    # 别名
    al = out.get("aliases")
    if isinstance(al, str):
        al = [al]
    if not isinstance(al, list) or len(al) < 2:
        warn(f"{tag}：aliases 少于 2 个（别名是检索召回的主要来源，建议补中文简称/英文名/牌号变体）")
    if isinstance(al, list):
        out["aliases"] = list(dict.fromkeys(str(x).strip() for x in al if str(x).strip()))

    # 区间
    for k in RANGE_KEYS:
        lo, hi = out.get(f"{k}_min"), out.get(f"{k}_max")
        for label, v in (("min", lo), ("max", hi)):
            if v is not None and not isinstance(v, (int, float)):
                err(f"{tag}：{k}_{label} 必须是数字（不要带单位），实际={v!r}")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
            err(f"{tag}：{k}_min({lo}) > {k}_max({hi})，区间反向")

    # 长期耐温硬约束
    limit, smax = out.get("service_temp_limit"), out.get("service_temp_max")
    if limit is None:
        err(f"{tag}：缺少 service_temp_limit（推荐算法的硬约束字段）")
    if smax is None:
        err(f"{tag}：缺少 service_temp_max")
    if isinstance(limit, (int, float)) and isinstance(smax, (int, float)) and limit != smax:
        err(f"{tag}：service_temp_limit({limit}) != service_temp_max({smax})——二者必须相等，"
            f"否则推荐结果与详情页展示会自相矛盾（请人工确认以哪个为准，本工具不擅自改数值）")

    # 注意项
    caut = out.get("cautions")
    if not isinstance(caut, list) or not caut:
        warn(f"{tag}：cautions 至少 1 条（详情页的红色警示区与推荐「注意事项」都取它）")
    elif not all(isinstance(c, dict) and c.get("content") for c in caut):
        warn(f"{tag}：cautions 元素必须是 {{\"type\":\"…\",\"content\":\"…\"}} 且 content 非空")

    # 失效模式
    lim = out.get("limitations")
    if not isinstance(lim, list) or not lim:
        warn(f"{tag}：limitations 至少 1 条，且要写真实使用限制（不是优点的反写）")

    # 溯源
    if not out.get("source"):
        warn(f"{tag}：缺少 source（数据出处），导入后无法溯源")
    if not out.get("source_date"):
        warn(f"{tag}：缺少 source_date（YYYY-MM-DD）")

    # 认证
    cert = out.get("certifications")
    if cert is not None and not isinstance(cert, dict):
        warn(f"{tag}：certifications 应是对象，已置空")
        out["certifications"] = None

    return out


PROC_SYNONYMS = {
    "注射成型": "注塑", "射出成型": "注塑", "injection molding": "注塑",
    "挤压成型": "挤出", "extrusion": "挤出", "中空成型": "吹塑",
    "压铸成型": "压铸", "die casting": "压铸", "钣金冲压": "冲压", "stamping": "冲压",
    "CNC加工": "机加工", "切削加工": "机加工",
}


def _pause_if_frozen(args) -> None:
    """打包成 exe 双击运行时，避免窗口一闪而过看不到结果。"""
    if getattr(sys, "frozen", False) and not getattr(args, "no_pause", False):
        try:
            input("\n按回车键退出…")
        except EOFError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="把大模型生成的材料 JSON 转成可导入材料包")
    ap.add_argument("input", nargs="?", help="输入 JSON 文件（支持带 ```json 围栏）")
    ap.add_argument("-o", "--output", help="输出材料包路径（默认 <输入名>_pack.json）")
    ap.add_argument("--check", action="store_true", help="只校验，不写出材料包")
    ap.add_argument("--no-pause", action="store_true", help="结束后不等待回车（脚本调用用）")
    args = ap.parse_args()

    frozen = getattr(sys, "frozen", False)
    if not args.input:
        print("用法： 把 JSON 文件拖到本程序的【图标】上（会以该文件启动新进程），或：")
        print("  MatSelectPackTool.exe 你的文件.json [-o 输出.json] [--check]")
        if frozen:
            print()
            print("提示：拖到【已经打开的本窗口】里是收不到文件的——")
            print("      那样只会把文件路径当文本粘贴进窗口。")
        if frozen:
            _pause_if_frozen(args)
        return 2

    src = Path(args.input)
    if not src.exists():
        print(f"[ERROR] 文件不存在：{src}")
        _pause_if_frozen(args)
        return 2

    # load_input 解析失败会抛 SystemExit；任何未捕获异常也不允许静默——
    # 全部拦到这里打印后统一 pause，避免 exe 窗口一闪而过看不到原因。
    try:
        code = _run(src, args)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 2
    except Exception:  # noqa: BLE001
        import traceback

        print("\n[ERROR] 处理过程中出现未预期异常：")
        traceback.print_exc()
        code = 2
    _pause_if_frozen(args)
    return code


def _run(src: Path, args) -> int:
    raw = load_input(src)
    mats = []
    for i, m in enumerate(raw):
        n = normalize_one(i, m)
        if n:
            mats.append(n)

    print("=" * 68)
    print(f"输入：{src}  共 {len(raw)} 条 → 有效 {len(mats)} 条")
    print("=" * 68)

    if warnings:
        print(f"\n[WARN] {len(warnings)} 条（可继续导入，建议逐条确认）：")
        for w in warnings[:40]:
            print("  · " + w)
        if len(warnings) > 40:
            print(f"  … 其余 {len(warnings) - 40} 条略")

    if errors:
        print(f"\n[ERROR] {len(errors)} 条（**必须修复后再导入**，不生成材料包）：")
        for e in errors:
            print("  ✗ " + e)
        return 1

    # 生成材料包（复用后端同一算法，保证校验和一致）
    try:
        from app.services.io_service import pack_checksum  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] 无法加载后端校验和算法（{exc}）。请在项目根目录运行本脚本。")
        return 2

    pack = {
        "pack_version": 1,
        "exported_at": None,  # 占位，下面用后端 now_iso
        "exported_by": "由大模型生成 + make_pack 规范化",
        "material_count": len(mats),
        "checksum": pack_checksum(mats),
        "materials": mats,
    }
    try:
        from app.db.connection import now_iso  # type: ignore

        pack["exported_at"] = now_iso()
    except Exception:  # noqa: BLE001
        pack["exported_at"] = ""

    if not warnings:
        print("\n[OK] 校验通过，无警告。")

    if args.check:
        print("\n（--check 模式：未写出文件）")
        return 0

    out = Path(args.output) if args.output else src.with_name(src.stem + "_pack.json")
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 已生成材料包：{out}")
    print(f"     条数 {pack['material_count']} · 校验和 {pack['checksum'][:23]}…")
    print("\n下一步：打开应用 → 「数据分享」页 → 「导入材料包」→ 拖入该文件。")
    print("（v1.2.4 起，大模型原始 JSON 也可以直接拖入该导入区，无需先用本工具转换）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
