-- ============================================================
-- MatSelect 数据库 Schema（SQLite，冻结版）
-- 来源：PRD v0.2 §4.1 / §4.2 全量 DDL + 契约 §4.6(b) 支撑表
-- 全部使用 CREATE ... IF NOT EXISTS，保证幂等可重复执行
-- 时间统一由 Python now_iso() 写入（东八区 ISO），此处不写 SQL 默认值
-- ============================================================

-- -------------------- 材料主表（ PRD §4.1 ）--------------------
CREATE TABLE IF NOT EXISTS material (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    uid                  TEXT UNIQUE NOT NULL,   -- 全局唯一 ID，跨机器分享去重依据
    name                 VARCHAR(200) NOT NULL,
    short_name           VARCHAR(100),
    category_id          INTEGER REFERENCES category(id),
    grade_type           VARCHAR(50),
    aliases              TEXT,                   -- JSON 数组
    description          TEXT,

    density_min          REAL, density_max            REAL,
    tensile_strength_min REAL, tensile_strength_max   REAL,
    elastic_modulus_min  REAL, elastic_modulus_max    REAL,
    elongation_min       REAL, elongation_max         REAL,
    notch_impact_min     REAL, notch_impact_max       REAL,

    hdt_min              REAL, hdt_max               REAL,
    service_temp_min     REAL, service_temp_max      REAL,
    service_temp_limit   REAL,                              -- 长期使用温度上限（推荐核心字段）

    features             TEXT,    -- JSON 数组：主要特性标签
    cautions             TEXT,    -- JSON 数组：[{type, content}]

    applications         TEXT,    -- JSON 数组：典型应用场景
    price_min            REAL, price_max REAL,
    price_unit           VARCHAR(30),
    price_note           TEXT,
    molding_process      TEXT,    -- JSON 数组：推荐成型工艺

    certifications       TEXT,    -- JSON：{ul94, ul_yellow_card, rohs, reach, iatf}
    limitations          TEXT,    -- JSON 数组：失效模式 / 不适用场景
    source               VARCHAR(500),
    source_date          DATE,
    value_type           VARCHAR(20),   -- typical / guaranteed

    archived             BOOLEAN DEFAULT 0,
    created_at           TIMESTAMP,
    updated_at           TIMESTAMP
);

-- -------------------- 全文检索（FTS5，trigram 对中文友好）--------------------
-- 分词器先写 trigram；init_db.py 会做能力探测，不支持则回退 unicode61 并重建
CREATE VIRTUAL TABLE IF NOT EXISTS material_fts USING fts5(
    name, short_name, aliases, description, applications,
    content='material', content_rowid='id', tokenize='trigram'
);

-- 三个同步触发器，保证 material_fts 与 material 一致
CREATE TRIGGER IF NOT EXISTS material_ai AFTER INSERT ON material BEGIN
    INSERT INTO material_fts(rowid, name, short_name, aliases, description, applications)
    VALUES (new.id, new.name, new.short_name, new.aliases, new.description, new.applications);
END;

CREATE TRIGGER IF NOT EXISTS material_ad AFTER DELETE ON material BEGIN
    INSERT INTO material_fts(material_fts, rowid, name, short_name, aliases, description, applications)
    VALUES ('delete', old.id, old.name, old.short_name, old.aliases, old.description, old.applications);
END;

CREATE TRIGGER IF NOT EXISTS material_au AFTER UPDATE ON material BEGIN
    INSERT INTO material_fts(material_fts, rowid, name, short_name, aliases, description, applications)
    VALUES ('delete', old.id, old.name, old.short_name, old.aliases, old.description, old.applications);
    INSERT INTO material_fts(rowid, name, short_name, aliases, description, applications)
    VALUES (new.id, new.name, new.short_name, new.aliases, new.description, new.applications);
END;

-- -------------------- 材料关系（一期仅建表，不做推理）--------------------
CREATE TABLE IF NOT EXISTS material_relation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER REFERENCES material(id),
    target_id   INTEGER REFERENCES material(id),
    rel_type    VARCHAR(50),
    note        TEXT
);

-- -------------------- 变更历史（支撑 D3 diff）--------------------
CREATE TABLE IF NOT EXISTS material_revision (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id  INTEGER REFERENCES material(id),
    snapshot     TEXT,         -- 变更前完整快照 JSON
    changed_at   TIMESTAMP,
    change_note  TEXT
);

-- -------------------- 选型任务（B5）--------------------
CREATE TABLE IF NOT EXISTS selection_task (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         VARCHAR(200),
    pinned        BOOLEAN DEFAULT 0,
    status        VARCHAR(20) DEFAULT 'active',
    created_at    TIMESTAMP,
    updated_at    TIMESTAMP,
    archived_at   TIMESTAMP
);

-- -------------------- 任务消息（对话流，B5 多轮追问）--------------------
CREATE TABLE IF NOT EXISTS task_message (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id) ON DELETE CASCADE,
    role          VARCHAR(20),
    content_json  TEXT,
    created_at    TIMESTAMP
);

-- -------------------- 待选材料（B6）--------------------
CREATE TABLE IF NOT EXISTS shortlist_item (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id) ON DELETE CASCADE,
    material_id   INTEGER REFERENCES material(id),
    user_note     TEXT,
    tag           VARCHAR(20) DEFAULT 'candidate',
    sort_order    INTEGER,
    added_at      TIMESTAMP,
    UNIQUE(task_id, material_id)
);

-- -------------------- 回评（C1）--------------------
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id),
    result        VARCHAR(20),
    reason_text   TEXT,
    reason_tags   TEXT,
    parsed_reason TEXT,
    created_at    TIMESTAMP
);

-- -------------------- 材料负面反馈（详情页提示 + 推荐降权）--------------------
CREATE TABLE IF NOT EXISTS material_negative_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id         INTEGER REFERENCES material(id),
    dimension           VARCHAR(50),
    reason              TEXT,
    source_feedback_id  INTEGER REFERENCES recommendation_feedback(id),
    weight              REAL DEFAULT 1.0,
    active              BOOLEAN DEFAULT 1,
    created_at          TIMESTAMP
);

-- -------------------- 需求缺口（知识盲区报告）--------------------
CREATE TABLE IF NOT EXISTS requirement_gap (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id),
    reason_text   TEXT,
    parsed_reason TEXT,
    resolved      BOOLEAN DEFAULT 0,
    created_at    TIMESTAMP
);

-- -------------------- 术语映射（同义词，B1 解析 + A3 检索）--------------------
CREATE TABLE IF NOT EXISTS term_alias (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    standard     VARCHAR(100),
    synonym      VARCHAR(100),
    type         VARCHAR(50)
);

-- -------------------- 支撑表（契约 §4.6(b)，PRD 未给，由架构师定义）--------------------
CREATE TABLE IF NOT EXISTS category (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL,
    parent_id   INTEGER REFERENCES category(id),
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TIMESTAMP NOT NULL,
    action    VARCHAR(50) NOT NULL,
    target    VARCHAR(200),
    detail    TEXT
);

CREATE TABLE IF NOT EXISTS settings_kv (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_staging (
    token       VARCHAR(64) PRIMARY KEY,
    payload     TEXT NOT NULL,
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_meta (
    key   VARCHAR(100) PRIMARY KEY,
    value TEXT
);

-- -------------------- 索引（uid 唯一已由列约束保证）--------------------
CREATE INDEX IF NOT EXISTS idx_material_category     ON material(category_id);
CREATE INDEX IF NOT EXISTS idx_material_service_temp  ON material(service_temp_limit);
CREATE INDEX IF NOT EXISTS idx_material_archived      ON material(archived);
CREATE INDEX IF NOT EXISTS idx_shortlist_task        ON shortlist_item(task_id);
CREATE INDEX IF NOT EXISTS idx_negative_material     ON material_negative_feedback(material_id);
CREATE INDEX IF NOT EXISTS idx_category_parent       ON category(parent_id);
CREATE INDEX IF NOT EXISTS idx_task_message_task     ON task_message(task_id);
CREATE INDEX IF NOT EXISTS idx_feedback_task         ON recommendation_feedback(task_id);
