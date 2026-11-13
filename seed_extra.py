"""补充自重动作，让「家里（自重）」场景可用。

原库按健身房造，自重动作只覆盖了胸和背，腿一个都没有。
这个脚本只做补充，不修改已有数据，可重复执行（INSERT OR IGNORE + name UNIQUE）。
"""

from db import get_conn

EXTRA = [
    # ---- 腿：自重 ----
    ("自重深蹲", "腿", "自重", "入门", "legs", "高脚杯深蹲"),
    ("自重箭步蹲", "腿", "自重", "入门", "legs", "哑铃箭步蹲"),
    ("靠墙静蹲", "腿", "自重", "入门", "legs", "腿举"),
    ("臀桥", "腿", "自重", "入门", "legs", "杠铃臀桥"),
    ("单腿臀桥", "腿", "自重", "中阶", "legs", "杠铃臀推"),
    ("自重提踵", "腿", "自重", "入门", "legs", "站姿提踵"),
    ("台阶上步", "腿", "自重", "入门", "legs", "保加利亚分腿蹲"),
    ("深蹲跳", "腿", "自重", "中阶", "legs", "杠铃深蹲"),
    ("单腿罗马尼亚硬拉", "腿", "自重", "中阶", "legs", "罗马尼亚硬拉"),
    ("滑行腿弯举", "腿", "自重", "高阶", "legs", "腿弯举"),
    # ---- 推：自重补肩 ----
    ("派克俯卧撑", "肩", "自重", "中阶", "push", "坐姿杠铃推举"),
    ("椅上臂屈伸", "手臂", "自重", "入门", "push", "绳索下压"),
    # ---- 拉：自重补背和肩 ----
    ("反向划船", "背", "自重", "中阶", "pull", "坐姿绳索划船"),
    ("超人式", "背", "自重", "入门", "pull", "直臂下压"),
    ("俯卧 Y 字抬臂", "肩", "自重", "入门", "pull", "面拉"),
    ("门框等长弯举", "手臂", "自重", "入门", "pull", "哑铃弯举"),
]


def main() -> None:
    conn = get_conn()
    try:
        before = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO exercises "
            "(name, muscle, equipment, difficulty, pattern, alternative) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            EXTRA,
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        print(f"动作库：{before} → {after}（新增 {after - before} 条）")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
