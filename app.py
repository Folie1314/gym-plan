"""Streamlit 界面 —— Day5-B：状态保存 + 输入 + 报错兜底。

启动：
    streamlit run app.py
"""

from datetime import datetime

import streamlit as st

from planner import PATTERN_CN, decide_pattern, generate, save_plan

st.set_page_config(page_title="今日训练", page_icon="🏋️")

st.title("今日训练计划")

# ---------- 1. 侧边栏输入 ----------
with st.sidebar:
    st.header("你的情况")
    goal = st.selectbox("目标", ["增肌", "减脂", "力量"])
    equipment = st.selectbox(
        "场地器械",
        ["健身房（器械齐全）", "家里（哑铃）", "家里（自重）"],
    )
    status = st.radio("今天状态", ["正常", "累", "精力充沛"], horizontal=True)
    st.divider()
    want_save = st.checkbox("生成后写入训练记录", value=False)

profile = {"goal": goal, "equipment": equipment, "status": status}

# ---------- 2. 今天该练什么 ----------
pattern = decide_pattern()
st.caption(f"今天该练：{PATTERN_CN[pattern]}")

# ---------- 3. 用 session_state 保留上一次的结果 ----------
if "plan" not in st.session_state:
    st.session_state.plan = None
    st.session_state.plan_at = ""

left, right = st.columns([1, 3])
with left:
    clicked = st.button("生成计划", type="primary", use_container_width=True)
with right:
    if st.session_state.plan:
        st.caption(
            f"当前显示的是 {st.session_state.plan_at} 生成的计划"
            f"（重试 {st.session_state.plan.get('_attempts', 1)} 次）"
        )

# ---------- 4. 生成：失败不许白屏 ----------
if clicked:
    with st.spinner("正在生成，约 3–5 秒…"):
        try:
            plan = generate(profile=profile)
        except Exception as exc:
            st.error(f"生成失败：{exc}")
            st.caption(
                "排查顺序：① 网络是否通 ② DeepSeek 余额是否够 "
                "③ 连续失败说明 prompt 或动作库有问题，不是网络问题"
            )
        else:
            st.session_state.plan = plan
            st.session_state.plan_at = datetime.now().strftime("%m-%d %H:%M:%S")
            if want_save:
                n = save_plan(plan)
                st.success(f"已写入 {n} 条训练记录")

# ---------- 5. 展示 ----------
plan = st.session_state.plan
if plan:
    st.divider()
    st.subheader(f"{PATTERN_CN[plan['pattern']]} · {len(plan['exercises'])} 个动作")
    for item in plan["exercises"]:
        st.markdown(f"**{item['name']}**　{item['sets']} 组 × {item['reps']} 次")
        if item.get("note"):
            st.caption(item["note"])
else:
    st.info("还没有计划。左边填好情况，点「生成计划」。")
