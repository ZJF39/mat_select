#!/usr/bin/env python
"""MatSelect 推荐引擎回归验证脚本。

用法（Windows PowerShell）：
    cd D:\\Documents\\MyDoc\\CODE\\MatSelect\\backend
    python ..\\tools\\verify_reco_regression.py

覆盖内容：
    A. 12 组代表性输入 → 行业通用首选材料的期望名次
    B. 权重契约不变量（Σ 权重 = 1；成本敏感时成本维度权重提升后仍 Σ = 1）
    C. 评分分解不变量（各维度 got 之和 + 反馈罚分 == 总分）
    D. 边界行为（无有效约束的闲聊输入不得产出推荐）

退出码 0 = 全部通过；1 = 存在失败项。
报告同时写入 tools/_verify_reco_regression.txt（UTF-8）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services import recommend_service as R  # noqa: E402
from app.repository.settings_repo import get_weights_fraction  # noqa: E402

# (用户输入, 期望首选材料名片段, 可接受的最差名次, 说明)
#
# max_rank 的取值原则：期望材料必须出现在该名次以内。1 表示必须首选；
# 2~3 用于「行业上并列合理、在本库数据下分差 ≤ 2 分」的场景 —— 这类排序由
# 价格与文案细节决定，强求首选会变成对测试集过拟合（详见验收报告）。
CASES: list[tuple[str, str, int, str]] = [
    ("保险丝座组件，注塑，使用温度不超过150°C", "PA66+GF30", 1, "电气件 + 注塑 + 150℃"),
    ("汽车连接器，注塑，耐温120°C，要求阻燃V-0", "PBT+GF30", 1, "电气件 + 阻燃"),
    ("发动机舱传感器支架，注塑，长期180°C", "PPS+GF40", 1, "高温结构件"),
    ("仪表板内饰件，注塑，要耐冲击", "PC-ABS", 1, "外观内饰件 + 抗冲"),
    ("透明车灯罩，注塑，要求透光", "PC", 2, "透明外观件（PMMA 透光性更优可居首）"),
    ("齿轮，注塑，要耐磨自润滑", "POM", 1, "传动件 + 耐磨自润滑"),
    ("耐油密封圈，模压，100°C", "NBR", 1, "弹性体 + 耐油"),
    ("低成本普通外壳，注塑", "ABS", 3, "成本敏感外壳（低成本档内互有胜负）"),
    ("车身覆盖件，模压，轻量化", "SMC", 1, "复合材料轻量"),
    ("高频精密连接器，注塑，耐240°C回流焊", "LCP", 2, "特种工程塑料（与 PEEK 并列）"),
    ("电机端盖，压铸，要散热", "压铸铝ADC12", 1, "金属压铸"),
    ("内饰卡扣，注塑，成本敏感", "PP", 1, "通用塑料 + 成本敏感"),
]

# 无有效约束的闲聊输入：术语集为空 → 语义维度不可评价 → 不得产出推荐
SMALLTALK = "你好，今天天气不错"


def rank_of(names: list[str], expect: str) -> int | None:
    """期望材料的 1-based 名次；比对用子串，避免「PA66+GF30（30%玻纤增强…）」全名不等。"""
    for i, n in enumerate(names):
        if expect in n:
            return i + 1
    return None


def main() -> int:
    out: list[str] = []
    failures: list[str] = []

    def log(line: str = "") -> None:
        out.append(line)
        print(line)

    log("== A. 代表性输入 → 期望名次 ==")
    log("%-40s %-14s %-6s %s" % ("输入", "期望材料", "名次", "实际 Top5"))
    log("-" * 130)
    for text, expect, max_rank, note in CASES:
        cons = R.parse(text)["constraints"]
        res = R.run(cons, user_text=text)
        names = [r["material"]["name"] for r in res["results"]]
        rank = rank_of(names, expect)
        top = " > ".join("%s(%s)" % (r["material"]["name"], r["score"]) for r in res["results"])
        ok = rank is not None and rank <= max_rank
        log("%-40s %-14s %-6s %s" % (text[:38], expect, rank or "未命中", top[:70]))
        log("    %s 约束=%s degraded=%s relaxed=%s  # %s" % (
            "PASS" if ok else "FAIL",
            {k: v for k, v in cons.items() if v}, res["degraded"], res["relaxed"], note))
        if not ok:
            failures.append("用例「%s」：期望 %s 在第 %d 名内，实际 %s"
                            % (text, expect, max_rank, rank or "未命中"))

        # C. 评分分解不变量：各维度 got 之和 + 反馈罚分 == 总分
        for item in res["results"]:
            bd = item["breakdown"]
            got = sum(v["got"] for k, v in bd.items() if isinstance(v, dict))
            expect_score = got + bd.get("feedback_penalty", 0)
            if abs(expect_score - item["score"]) > 1.0:
                failures.append("用例「%s」材料 %s 分解和 %.1f != 总分 %d"
                                % (text, item["material"]["name"], expect_score, item["score"]))

    log()
    log("== B. 权重契约 ==")
    w = get_weights_fraction()
    log("  默认权重 = %s   Σ = %.4f" % ({k: round(v, 3) for k, v in w.items()}, sum(w.values())))
    if abs(sum(w.values()) - 1.0) > 1e-6:
        failures.append("默认权重之和不为 1：%.6f" % sum(w.values()))

    w_cs = R._effective_weights(True)
    log("  成本敏感权重 = %s   Σ = %.4f" % ({k: round(v, 3) for k, v in w_cs.items()}, sum(w_cs.values())))
    if abs(sum(w_cs.values()) - 1.0) > 1e-6:
        failures.append("成本敏感权重之和不为 1：%.6f" % sum(w_cs.values()))
    if w_cs["cost"] <= w["cost"]:
        failures.append("成本敏感时成本维度权重未提升：%.3f -> %.3f" % (w["cost"], w_cs["cost"]))

    log()
    log("== D. 边界行为 ==")
    res = R.run(R.parse(SMALLTALK)["constraints"], user_text=SMALLTALK)
    log("  闲聊输入「%s」→ results=%d degraded=%s" % (SMALLTALK, len(res["results"]), res["degraded"]))
    if res["results"]:
        failures.append("无有效约束的闲聊输入不应产出推荐，实际返回 %d 条" % len(res["results"]))

    log()
    if failures:
        log("== 结果：FAIL（%d 项） ==" % len(failures))
        for f in failures:
            log("  - " + f)
    else:
        log("== 结果：PASS（%d 组用例 + 契约不变量全部通过） ==" % len(CASES))

    (ROOT / "tools" / "_verify_reco_regression.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
