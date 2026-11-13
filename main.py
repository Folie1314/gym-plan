"""命令行入口：生成今天的训练计划。

用法：
    python main.py              生成，不保存
    python main.py --save       生成并写入训练历史
    python main.py --pattern legs   强制指定分化
"""

import argparse
import json

from db import init_db
from planner import PATTERN_CN, decide_pattern, generate, save_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="生成今天的训练计划")
    parser.add_argument("--save", action="store_true", help="把计划写入训练历史")
    parser.add_argument(
        "--pattern",
        choices=["push", "pull", "legs"],
        help="强制指定分化，不指定则自动推断",
    )
    args = parser.parse_args()

    init_db()

    pattern = args.pattern or decide_pattern()
    print(f"今天练：{pattern} —— {PATTERN_CN[pattern]}")

    plan = generate(pattern)
    print(f"校验通过（第 {plan['_attempts']} 次尝试）")
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    if args.save:
        count = save_plan(plan)
        print(f"\n已写入训练历史：{count} 条")
    else:
        print("\n（未保存。加 --save 才会写入历史）")


if __name__ == "__main__":
    main()
