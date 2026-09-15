# -*- coding: utf-8 -*-
"""种子 → 已初始化数据库 的增量同步工具。

背景：init_db.seed_if_empty() 只在表为空时导入 data/materials.json 等种子。
exe 绑定 `<exe同级>\\data\\matselect.db`，若该目录已存在旧版本生成的库，
种子更新（如 v1.2.1 扩充到 200 条）不会自动进入旧库。本工具按
「名称 upsert + 术语 (standard,synonym) upsert + 分类补齐」把种子同步进
任意已初始化库，且不破坏库内用户数据（任务/反馈/归档状态保留）。

用法：
  python tools/sync_seed_db.py [db_path] [--seed seed_dir]
默认 db_path=data/matselect.db，seed_dir=data。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JSON_COLS = {"aliases", "features", "cautions", "applications",
             "molding_process", "certifications", "limitations"}
JSON_OBJ_COLS = {"certifications"}


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "matselect.db"
    seed_dir = Path(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv \
        else REPO / "data"
    now = "2026-09-15T12:10:00"

    mats = (json.loads((seed_dir / "materials.json").read_text(encoding="utf-8"))
            .get("materials", []))
    aliases = (json.loads((seed_dir / "term_alias.json").read_text(encoding="utf-8"))
               .get("aliases", []))
    cats = json.loads((seed_dir / "categories.json").read_text(encoding="utf-8"))["categories"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(material)")]

    # ---- 分类补齐（两级树；叶名 → id）----
    cat_map = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM category")}
    max_sort = conn.execute("SELECT MAX(sort_order) FROM category").fetchone()[0] or 0
    cats_added = 0
    for parent in cats:
        pname = str(parent["name"])
        if pname not in cat_map:
            max_sort += 1
            cur = conn.execute(
                "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
                (pname, None, max_sort, now))
            cat_map[pname] = cur.lastrowid
            cats_added += 1
        for child in parent.get("children", []):
            cname = str(child["name"])
            if cname in cat_map:
                continue
            max_sort += 1
            cur = conn.execute(
                "INSERT INTO category(name, parent_id, sort_order, created_at) VALUES (?,?,?,?)",
                (cname, cat_map[pname], max_sort, now))
            cat_map[cname] = cur.lastrowid
            cats_added += 1
    conn.commit()

    # ---- 材料按名称 upsert ----
    ins = upd = 0
    for m in mats:
        name = str(m.get("name") or "").strip()
        if not name:
            continue
        row = {}
        for k, v in m.items():
            if k == "category_path" or k not in cols:
                continue
            if k in JSON_COLS:
                if v is None:
                    v = {} if k in JSON_OBJ_COLS else []
                row[k] = json.dumps(v, ensure_ascii=False)
            else:
                row[k] = v
        row["name"] = name
        if row.get("category_id") in (None, 0):
            row["category_id"] = cat_map.get(str((m.get("category_path") or [])[-1]))

        exist = conn.execute("SELECT id FROM material WHERE name=?", (name,)).fetchone()
        if exist:
            sets, vals = [], []
            for k, v in row.items():
                if k == "name":
                    continue
                sets.append(f"{k}=?")
                vals.append(v)
            vals.append(exist["id"])
            conn.execute(f"UPDATE material SET {','.join(sets)} WHERE id=?", tuple(vals))
            upd += 1
        else:
            row.setdefault("uid", m.get("uid"))
            if "archived" in cols:
                row.setdefault("archived", 0)
            if "created_at" in cols:
                row.setdefault("created_at", now)
            if "updated_at" in cols:
                row.setdefault("updated_at", now)
            keys = [k for k in row if k in cols]
            conn.execute(
                f"INSERT INTO material ({','.join(keys)}) VALUES ({','.join('?'*len(keys))})",
                tuple(row[k] for k in keys))
            ins += 1
    conn.commit()

    # ---- 术语按 (standard, synonym) upsert ----
    ta_cols = [r["name"] for r in conn.execute("PRAGMA table_info(term_alias)")]
    t_ins = 0
    for a in aliases:
        std, syn = a.get("standard"), a.get("synonym")
        if not std or not syn:
            continue
        row_ = conn.execute("SELECT id FROM term_alias WHERE standard=? AND synonym=?",
                            (std, syn)).fetchone()
        if row_:
            conn.execute("UPDATE term_alias SET type=? WHERE id=?", (a["type"], row_["id"]))
            continue
        kv = {"standard": std, "synonym": syn, "type": a["type"]}
        if "created_at" in ta_cols:
            kv["created_at"] = now
        keys = [k for k in kv if k in ta_cols]
        conn.execute(
            f"INSERT INTO term_alias ({','.join(keys)}) VALUES ({','.join('?'*len(keys))})",
            tuple(kv[k] for k in keys))
        t_ins += 1
    conn.commit()

    db_m = conn.execute("SELECT COUNT(*) FROM material").fetchone()[0]
    db_t = conn.execute("SELECT COUNT(*) FROM term_alias").fetchone()[0]
    db_c = conn.execute("SELECT COUNT(*) FROM category").fetchone()[0]
    missing = [m["name"] for m in mats
               if not conn.execute("SELECT 1 FROM material WHERE name=?",
                                   (m["name"],)).fetchone()]
    conn.close()

    print(f"[{db_path}] 分类补 {cats_added} | 材料插入 {ins} / 更新 {upd} | 术语补 {t_ins}")
    print(f"同步后：材料={db_m} 术语={db_t} 分类={db_c}")
    if missing:
        print(f"[警告] 仍有 {len(missing)} 条种子材料未入库: {missing[:5]}")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
