import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"D:\Documents\MyDoc\CODE\MatSelect\data\matselect.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("== 计数 ==")
for t in ("category", "material", "term_alias", "settings_kv", "app_meta"):
    print(f"  {t} = {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")

print("== 分类树（一级） ==")
for r in c.execute("SELECT name FROM category WHERE parent_id IS NULL ORDER BY sort_order"):
    print("  -", r["name"])

print("== 材料抽样 ==")
for r in c.execute("SELECT name, service_temp_limit, price_unit, category_id FROM material ORDER BY id LIMIT 5"):
    print("  ", dict(r))

print("== 分类挂载率 ==")
n_null = c.execute("SELECT COUNT(*) FROM material WHERE category_id IS NULL").fetchone()[0]
print("  category_id 为空:", n_null, "/ 50")

print("== 术语 type 分布 ==")
for r in c.execute("SELECT type, COUNT(*) AS n FROM term_alias GROUP BY type"):
    print("  ", r["type"], r["n"])

print("== FTS 检索（trigram，中文子串） ==")
for q in ("PP", "保险丝座", "注塑", "PA66"):
    try:
        n = c.execute("SELECT COUNT(*) FROM material_fts WHERE material_fts MATCH ?", (q,)).fetchone()[0]
        print(f"  MATCH {q!r} -> {n}")
    except Exception as e:
        print(f"  MATCH {q!r} -> ERR {e}")

print("== 硬约束过滤（温度>=150 且含注塑） ==")
rows = c.execute(
    "SELECT COUNT(*) FROM material WHERE service_temp_limit >= 150 AND molding_process LIKE '%注塑%' AND archived = 0"
).fetchone()[0]
print("  命中:", rows)

print("== 索引数 ==")
idx = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex%'")]
print("  ", len(idx))
c.close()
