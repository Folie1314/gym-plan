-- 动作库：静态字典，只读。
-- 造一次，之后只查询，不改动。
CREATE TABLE IF NOT EXISTS exercises (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    muscle      TEXT    NOT NULL,
    equipment   TEXT    NOT NULL,
    difficulty  TEXT    NOT NULL,
    pattern     TEXT    NOT NULL,
    alternative TEXT
);

-- 训练历史：动态记录，每练一次就新增若干行。
CREATE TABLE IF NOT EXISTS sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    exercise_name TEXT    NOT NULL,
    sets          INTEGER NOT NULL,
    reps          INTEGER NOT NULL,
    weight_kg     REAL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 索引：加速「查最近几天练了什么」
CREATE INDEX IF NOT EXISTS idx_sessions_date    ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_exercises_pattern ON exercises(pattern);
