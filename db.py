"""数据库连接与初始化。"""

import sqlite3
from pathlib import Path

# 数据库文件固定在项目内的 data/ 目录下。
# 用 __file__ 定位，而不是写死 "data/gym.db"：
# 前者不管你在哪个目录运行脚本都能找对，后者依赖当前工作目录，换目录就崩。
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "gym.db"


def get_conn() -> sqlite3.Connection:
    """打开一个数据库连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # 默认查询结果是元组，只能 row[0]、row[1]。
    # 开启 Row 之后可以 row["name"]，代码可读性差很多，也抗字段顺序变化。
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表。重复执行安全（schema 里全是 IF NOT EXISTS）。"""
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")

    conn = get_conn()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        # sqlite3 的连接必须显式关闭，with 语句只负责事务提交，不负责关闭。
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"数据库已初始化：{DB_PATH}")
