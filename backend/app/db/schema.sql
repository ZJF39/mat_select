-- MatSelect 数据库结构（PRD §4.1 / §4.2 + 契约 §4.6(b)）
-- 由 db/init_db.py 在首次启动时执行；trigram 不支持时自动回退 unicode61。

CREATE TABLE IF NOT EXISTS category (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL,
    parent_id   INTEGER REFERENCES category(id),
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS material (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    uid                  TEXT UNIQUE NOT NULL,
    name                 VARCHAR(200) NOT NULL,
    short_name           VARCHAR(100),
    category_id          INTEGER REFERENCES category(id),
    grade_type           VARCHAR(50),
    aliases              TEXT,
    description          TEXT,

    density_min          REAL, density_max          REAL,
    tensile_strength_min REAL, tensile_strength_max REAL,
    elastic_modulus_min  REAL, elastic_modulus_max  REAL,
    elongation_min       REAL, elongation_max       REAL,
    notch_impact_min     REAL, notch_impact_max     REAL,

    hdt_min              REAL, hdt_max              REAL,
    service_temp_min     REAL, service_temp_max     REAL,
    service_temp_limit   REAL,

    features             TEXT,
    cautions             TEXT,

    applications         TEXT,
    price_min            REAL, price_max            REAL,
    price_unit           VARCHAR(30),
    price_note           TEXT,
    molding_process      TEXT,

    certifications       TEXT,
    limitations          TEXT,
    source               VARCHAR(500),
    source_date          DATE,
    value_type           VARCHAR(20) DEFAULT 'typical',

    archived             BOOLEAN DEFAULT 0,
    created_at           TIMESTAMP,
    updated_at           TIMESTAMP
);

-- 全文检索（trigram 分词，对中文子串友好）
CREATE VIRTUAL TABLE IF NOT EXISTS material_fts USING fts5(
    name, short_name, aliases, description, applications,
    content='material', content_rowid='id', tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS material_relation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER REFERENCES material(id),
    target_id   INTEGER REFERENCES material(id),
    rel_type    VARCHAR(50),
    note        TEXT
);

CREATE TABLE IF NOT EXISTS material_revision (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id  INTEGER REFERENCES material(id),
    snapshot     TEXT,
    changed_at   TIMESTAMP,
    change_note  TEXT
);

CREATE TABLE IF NOT EXISTS selection_task (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        VARCHAR(200),
    pinned       BOOLEAN DEFAULT 0,
    status       VARCHAR(20) DEFAULT 'active',
    created_at   TIMESTAMP,
    updated_at   TIMESTAMP,
    archived_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_message (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER REFERENCES selection_task(id) ON DELETE CASCADE,
    role         VARCHAR(20),
    content_json TEXT,
    created_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shortlist_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER REFERENCES selection_task(id) ON DELETE CASCADE,
    material_id  INTEGER REFERENCES material(id),
    user_note    TEXT,
    tag          VARCHAR(20) DEFAULT 'candidate',
    sort_order   INTEGER,
    added_at     TIMESTAMP,
    UNIQUE(task_id, material_id)
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id),
    result        VARCHAR(20),
    reason_text   TEXT,
    reason_tags   TEXT,
    parsed_reason TEXT,
    created_at    TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS requirement_gap (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER REFERENCES selection_task(id),
    reason_text   TEXT,
    parsed_reason TEXT,
    resolved      BOOLEAN DEFAULT 0,
    created_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS term_alias (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    standard  VARCHAR(100),
    synonym   VARCHAR(100),
    type      VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS operation_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TIMESTAMP NOT NULL,
    action    VARCHAR(50) NOT NULL,
    target    VARCHAR(200),
    detail    TEXT
);

CREATE TABLE IF NOT EXISTS settings_kv (
    key        VARCHAR(100) PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP
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

-- FTS5 触发器：保持 material_fts 与 material 同步
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

-- 显式索引（契约要求；schema 重写时曾被遗漏，本轮补齐）
-- uid 唯一性已由 material.uid TEXT UNIQUE NOT NULL 覆盖，不再重复建索引。
CREATE INDEX IF NOT EXISTS idx_material_category    ON material(category_id);
CREATE INDEX IF NOT EXISTS idx_material_temp_limit  ON material(service_temp_limit);
CREATE INDEX IF NOT EXISTS idx_material_archived    ON material(archived);
CREATE INDEX IF NOT EXISTS idx_material_name        ON material(name);
CREATE INDEX IF NOT EXISTS idx_category_parent      ON category(parent_id);
CREATE INDEX IF NOT EXISTS idx_revision_material    ON material_revision(material_id);
CREATE INDEX IF NOT EXISTS idx_task_status_updated  ON selection_task(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_message_task         ON task_message(task_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_task       ON shortlist_item(task_id);
CREATE INDEX IF NOT EXISTS idx_negative_material    ON material_negative_feedback(material_id, dimension, active);
CREATE INDEX IF NOT EXISTS idx_gap_task             ON requirement_gap(task_id);
