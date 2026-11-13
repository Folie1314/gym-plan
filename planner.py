"""核心逻辑：决定今天练什么 → 筛候选动作 → 拼 prompt → 生成计划 → 校验。

设计要点：
1. 时区固定按北京时间（+8）计算，不依赖运行机器的本地时区。
2. USE_FAKE = True 时不调模型，用假数据跑通链路；改成 False 才真调用。
3. 模型返回的动作必须在候选列表里，否则判定失败并重试。
"""

import json
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from openai import OpenAI

from db import get_conn

load_dotenv()

# 为什么用固定 +8 而不是 zoneinfo("Asia/Shanghai")：
# Windows 没有系统时区数据库，zoneinfo 需要额外安装 tzdata 包。
# 中国不实行夏令时，固定偏移永远正确，省一个依赖。
CN_TZ = timezone(timedelta(hours=8))

CYCLE = ["push", "pull", "legs"]

# 场景 → 用户真正能用的器械。写死在代码里而不是读数据库：
# 这是「用户能力」的定义，属于程序配置，不属于动作数据。
SCENE_EQUIPMENT = {
    "健身房（器械齐全）": ("器械", "哑铃", "杠铃", "自重"),
    "家里（哑铃）": ("哑铃", "自重"),
    "家里（自重）": ("自重",),
}

# 少于这个数就排不出一份像样的计划，宁可明确报错也不硬生成
MIN_CANDIDATES = 4

PATTERN_CN = {
    "push": "推（胸、肩、三头）",
    "pull": "拉（背、二头、后肩）",
    "legs": "腿（股四、腘绳、臀、小腿）",
}

# 改成 False 就走真实的模型调用
USE_FAKE = False

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    timeout=60.0,
    max_retries=2,
)


def today_str() -> str:
    """今天，按北京时间。"""
    return datetime.now(CN_TZ).date().isoformat()


def recent_patterns(days: int = 2) -> list[str]:
    """最近几天练过的分化，最新的在前。

    sessions 表里没存 pattern，靠 JOIN exercises 推导出来。
    这样避免冗余：动作改了分类，历史记录自动跟着变。
    """
    since = (datetime.now(CN_TZ).date() - timedelta(days=days - 1)).isoformat()

    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT s.date, e.pattern
            FROM sessions s
            JOIN exercises e ON e.name = s.exercise_name
            WHERE s.date >= ?
            ORDER BY s.date DESC
            """,
            (since,),
        ).fetchall()
        return [row["pattern"] for row in rows]
    finally:
        conn.close()


def decide_pattern() -> str:
    """今天该练哪个分化。

    规则：最近两天没练过的，优先。都没练过就从推开始。
    """
    recent = recent_patterns()
    for pattern in CYCLE:
        if pattern not in recent:
            return pattern
    return CYCLE[0]


def equipment_for(scene: str) -> tuple[str, ...]:
    """把场景翻译成器械白名单。未知场景按健身房处理，不抛错。"""
    return SCENE_EQUIPMENT.get(scene, SCENE_EQUIPMENT["健身房（器械齐全）"])


def candidates(
    pattern: str,
    equipment: tuple[str, ...] | None = None,
    per_muscle: int = 5,
    min_total: int = 12,
) -> list[dict]:
    """按分化 + 器械筛候选动作，每个肌群均衡取样。

    两个坑都在这里踩过：
    1. 不能用简单的 LIMIT：push 有 26 个动作，id 靠前的全是胸，
       LIMIT 15 截下来三头一个都没有，模型只能全排胸部动作。
       用窗口函数按 muscle 分组，每组各取前 per_muscle 个。
    2. 器械条件必须落在 SQL 里，不能只写进 prompt。
       曾经 prompt 里写着「家里只有哑铃」，模型照样排杠铃划船——
       因为它只能从候选里挑，而候选里本来就有杠铃动作。

    兜底：legs 的动作 muscle 全是「腿」，只有一个分组，
    分组取会只剩 5 个。这种情况退回按难度取足 min_total 个（仍受器械约束）。
    """
    equipment = equipment or SCENE_EQUIPMENT["健身房（器械齐全）"]
    placeholders = ",".join("?" * len(equipment))
    where = f"pattern = ? AND equipment IN ({placeholders})"
    params = (pattern, *equipment)

    conn = get_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT name, muscle, equipment, difficulty
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY muscle ORDER BY difficulty, id
                       ) AS rn
                FROM exercises
                WHERE {where}
            )
            WHERE rn <= ?
            ORDER BY muscle, rn
            """,
            (*params, per_muscle),
        ).fetchall()

        if len(rows) < min_total:
            rows = conn.execute(
                f"""
                SELECT name, muscle, equipment, difficulty
                FROM exercises
                WHERE {where}
                ORDER BY difficulty, id
                LIMIT ?
                """,
                (*params, min_total),
            ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def last_weight(exercise_name: str) -> float | None:
    """这个动作上次用的重量。没有记录就返回 None（渐进超负荷的起点）。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT weight_kg FROM sessions WHERE exercise_name = ? "
            "ORDER BY date DESC, id DESC LIMIT 1",
            (exercise_name,),
        ).fetchone()
        return row["weight_kg"] if row else None
    finally:
        conn.close()


def build_prompt(
    pattern: str,
    cands: list[dict],
    recent: list[str],
    profile: dict | None = None,
) -> str:
    """把用户情况 + 候选动作拼成一段提示词。

    profile 允许为空：命令行 main.py 不传，行为跟以前一致。
    """
    names = "、".join(c["name"] for c in cands)
    recent_text = "；".join(recent) if recent else "无记录（今天开始）"

    profile = profile or {}
    goal = profile.get("goal", "增肌")
    equipment = profile.get("equipment", "健身房（器械齐全）")
    status = profile.get("status", "正常")

    return f"""你是一名力量训练教练。为今天设计一份训练计划。

【目标】{goal}
【场地器械】{equipment}
【今天状态】{status}
【今日分化】{pattern} —— {PATTERN_CN[pattern]}
【最近练过】{recent_text}
【可选动作】（只能从这里选，禁止发明新动作）
{names}

要求：
1. 选 4–6 个动作，覆盖不同肌群
2. 每个动作 3–4 组，8–12 次
3. 重量先填 0，表示由用户自己决定
4. 今天状态为「累」时，组数减到 2–3 组，不要硬冲
5. 只输出 JSON 本体，不要 markdown 代码块，不要任何解释

输出格式：
{{"pattern": "{pattern}", "exercises": [{{"name": "动作名", "sets": 3, "reps": 10, "weight_kg": 0, "note": "一句要点"}}]}}
"""


def _fake_model(prompt: str, pattern: str, cands: list[dict]) -> str:
    """假模型：不联网，直接按候选顺序取前 4 个。用来验证链路。"""
    picked = [
        {
            "name": c["name"],
            "sets": 3,
            "reps": 10,
            "weight_kg": 0,
            "note": "假数据：仅用于验证链路",
        }
        for c in cands[:4]
    ]
    return json.dumps({"pattern": pattern, "exercises": picked}, ensure_ascii=False)


def _real_model(prompt: str) -> str:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


def parse_and_validate(raw: str, allowed: set[str]) -> dict:
    """解析 JSON 并校验。任何一步不对都抛 ValueError，由上层重试。"""
    text = raw.strip()

    # 模型爱加 ```json 包装，先剥掉
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败：{exc.msg}") from exc

    items = plan.get("exercises")
    if not isinstance(items, list) or not items:
        raise ValueError("缺少 exercises 列表或为空")

    for item in items:
        name = item.get("name")
        if name not in allowed:
            raise ValueError(f"动作不在候选库中：{name}")

    return plan


def generate(
    pattern: str | None = None,
    profile: dict | None = None,
    max_retries: int = 3,
) -> dict:
    """生成今天的计划。返回解析并校验过的字典。"""
    profile = profile or {}
    pattern = pattern or decide_pattern()
    scene = profile.get("equipment", "健身房（器械齐全）")
    cands = candidates(pattern, equipment_for(scene))

    if len(cands) < MIN_CANDIDATES:
        raise RuntimeError(
            f"「{scene}」场景下 {PATTERN_CN[pattern]} 只有 {len(cands)} 个可用动作，"
            f"排不出一份计划。需要补动作库，不是模型的问题。"
        )

    allowed = {c["name"] for c in cands}
    prompt = build_prompt(pattern, cands, recent_patterns(), profile)

    last_err = None
    for attempt in range(1, max_retries + 1):
        raw = _fake_model(prompt, pattern, cands) if USE_FAKE else _real_model(prompt)
        try:
            plan = parse_and_validate(raw, allowed)
            plan["pattern"] = pattern
            plan["_attempts"] = attempt
            return plan
        except ValueError as exc:
            last_err = exc
            print(f"  第 {attempt} 次校验失败：{exc}")

    raise RuntimeError(f"重试 {max_retries} 次仍失败：{last_err}")


def save_plan(plan: dict, day: str | None = None) -> int:
    """把计划写进 sessions。返回写入的动作条数。"""
    day = day or today_str()

    conn = get_conn()
    try:
        rows = [
            (
                day,
                item["name"],
                int(item.get("sets", 3)),
                int(item.get("reps", 10)),
                float(item.get("weight_kg") or 0),
            )
            for item in plan["exercises"]
        ]
        conn.executemany(
            "INSERT INTO sessions (date, exercise_name, sets, reps, weight_kg) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()
