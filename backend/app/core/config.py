"""应用配置（契约 §3 / 架构约定）。

集中暴露后端各模块依赖的配置项。推荐权重与降权阈值的「默认值」在此定义，
运行时以 settings_kv 表中的数据为准（若无则回退到这里的默认值）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 应用版本（同时写入 app_meta，供 /api/health 读取）
# 与前端 NavRail 版本号、里程碑 tag 保持一致：
#   v1.0.0 = 一期验收交付；v1.2.0 = 材料库检索能力修复（模糊搜索/分类筛选/设置页/任务归档）
#   v1.2.1 = 种子扩至 200 条材料 + 术语库扩充；v1.2.2 = 材料库「加载更多」滚动位置修复
APP_VERSION = "1.2.2"

# ---------------------------------------------------------------------------
# 路径解析（同时支持「源码运行」与「PyInstaller 打包运行」）
#
# 两类路径必须分开，否则打包后会出现「读到只读解包目录 / 写不进去」：
#   BUNDLE_DIR（= PROJECT_ROOT）—— **只读**资源根：schema.sql、frontend/dist、
#                                  data/*.json 种子；打包后在 sys._MEIPASS 内。
#   APP_DIR                     —— **可写**根：SQLite 库、backups 目录；
#                                  打包后是 exe 所在目录（不能写 _MEIPASS，
#                                  onefile 退出时会清理该临时目录）。
# 非打包运行时两者都等于项目根，与打包前行为完全一致。
# ---------------------------------------------------------------------------
FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    APP_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parents[3]
    APP_DIR = BUNDLE_DIR

# 项目根（只读资源根）：main.py 用它定位 frontend/dist
PROJECT_ROOT = BUNDLE_DIR

# 数据目录（SQLite 库、备份）；可用 MATSELECT_DATA_DIR 覆盖
DATA_DIR = Path(os.environ.get("MATSELECT_DATA_DIR", str(APP_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 只读种子数据目录：打包时 data/*.json 随 exe 分发，首次启动从这里读取
SEED_DIR = BUNDLE_DIR / "data"

# 数据库文件位置（MATSELECT_DB 可覆盖，便于多数据目录测试）
DB_PATH = Path(os.environ.get("MATSELECT_DB", str(DATA_DIR / "matselect.db")))

# 服务监听
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8100"))

# CORS 允许来源：本地前端 dev server（vite 固定 127.0.0.1:5173）
# 注意：app/main.py:20 依赖本常量，缺失会导致应用导入失败。
_cors_env = os.environ.get("MATSELECT_CORS_ORIGINS", "")
CORS_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        f"http://{API_HOST}:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
)

# 推荐五维默认权重（契约 §5.3）；自动归一化后使用
DEFAULT_WEIGHTS = {
    "temp": 0.30,
    "semantic": 0.25,
    "cost": 0.20,
    "mechanics": 0.15,
    "process": 0.10,
}

# 反馈降权默认配置（契约 §5.2）
DEFAULT_PENALTY = {
    "threshold": 2,   # 单维度达到 THRESHOLD 次才生效（单条不计）
    "max": 15,        # PENALTY_MAX，单次评降上限
}

# 各维度降权权重（Σ 归一为 1），反馈降权公式中 DIM_WEIGHT[d]
PENALTY_DIM_WEIGHTS = {
    "温度": 0.30,
    "工艺": 0.20,
    "成本": 0.25,
    "外观": 0.10,
    "参数准确性": 0.15,
}

# 维度中文标签（供设置页 / 解释展示）
WEIGHT_LABELS = {
    "temp": "温度裕度",
    "semantic": "语义匹配",
    "cost": "成本契合",
    "mechanics": "力学契合",
    "process": "工艺契合",
}

WEIGHT_HINTS = {
    "temp": "需求温度与材料长期耐温上限的裕度",
    "semantic": "用户描述与材料场景/特性的文本相似度",
    "cost": "参考价与预算的契合度",
    "mechanics": "按零件类型加权的力学/特性契合",
    "process": "成型工艺匹配程度",
}

# 降权生效阈值 / 上限的键名
PENALTY_KEY = "feedback_penalty"
WEIGHTS_KEY = "weights"
