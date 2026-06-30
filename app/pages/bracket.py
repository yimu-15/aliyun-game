"""
淘汰赛对阵树/赛程树可视化 (5)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from app.components.bracket_tree import render_bracket_tree


def render(results, team_map, groups):
    st.markdown('<div class="main-title">🌳 淘汰赛对阵树</div>', unsafe_allow_html=True)
    st.caption("交互式赛程树 — 悬停查看详情 | 支持缩放和平移")

    # 对阵树可视化
    render_bracket_tree(results, team_map, groups)

    st.markdown("---")

    # 逐轮展开
    st.subheader("📋 逐轮预测详情")

    top_teams = []
    for r in results:
        name = r.team_name or r.team_id
        top_teams.append({
            "id": r.team_id, "name": name,
            "prob": r.champion_prob,
            "final": r.final_prob,
            "semi": r.semi_prob,
            "quarter": r.quarter_prob,
            "round_16": r.round_16_prob,
        })

    # 晋级概率热力图
    st.markdown("### 🔥 各队晋级各轮概率")

    if top_teams:
        stages = ["16强", "8强", "半决赛", "决赛", "夺冠"]
        heat_data = []
        for t in top_teams[:12]:
            heat_data.append({
                "球队": t["name"],
                "16强": t.get("round_16", 0),
                "8强": t.get("quarter", 0),
                "半决赛": t.get("semi", 0),
                "决赛": t.get("final", 0),
                "夺冠": t["prob"],
            })

        df_heat = pd.DataFrame(heat_data).set_index("球队")

        fig = go.Figure(data=go.Heatmap(
            z=df_heat.values,
            x=df_heat.columns,
            y=df_heat.index,
            colorscale="Blues",
            text=[[f"{v:.1%}" for v in row] for row in df_heat.values],
            texttemplate="%{text}",
            textfont={"size": 11},
            hoverongaps=False,
        ))
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(side="top"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # 逐轮展开
    st.markdown("---")
    st.markdown("### 📑 各轮对阵展开")

    n_rounds = min(4, _calc_rounds_count(len(top_teams)))
    round_labels = ["16强 → 8强", "8强 → 半决赛", "半决赛 → 决赛", "决赛"]

    for rnd in range(n_rounds):
        with st.expander(f"🔽 {round_labels[rnd] if rnd < len(round_labels) else f'第{rnd+1}轮'}", expanded=rnd == 0):
            # 模拟该轮可能的对阵
            teams_in_round = top_teams[:max(4, 2**(n_rounds - rnd))]
            if len(teams_in_round) >= 2:
                matches = []
                for i in range(0, len(teams_in_round)-1, 2):
                    a = teams_in_round[i]
                    b = teams_in_round[min(i+1, len(teams_in_round)-1)]
                    prob_vals = _calc_match_probs(a, b, team_map)
                    matches.append({
                        "主队": a["name"],
                        "客队": b["name"],
                        "主胜": prob_vals["p_home"],
                        "平局": prob_vals["p_draw"],
                        "客胜": prob_vals["p_away"],
                        "主晋级": prob_vals["p_advance_a"],
                    })

                df_m = pd.DataFrame(matches)
                st.dataframe(df_m, use_container_width=True, hide_index=True)


def _calc_rounds_count(n_teams: int) -> int:
    r = 0
    while n_teams >= 2:
        r += 1
        n_teams //= 2
    return max(r, 1)


def _calc_match_probs(team_a: dict, team_b: dict, team_map: dict) -> dict:
    """计算两队对阵的胜平负和晋级概率"""
    ta = team_map.get(team_a["id"])
    tb = team_map.get(team_b["id"])
    if ta and tb:
        from models.group_stage import predict_match
        from models.knockout import calc_advance_probability
        pred = predict_match(ta, tb)
        adv_a = calc_advance_probability(ta, tb)
        return {
            "p_home": f"{pred.p_home_win:.1%}",
            "p_draw": f"{pred.p_draw:.1%}",
            "p_away": f"{pred.p_away_win:.1%}",
            "p_advance_a": f"{adv_a:.1%}",
        }
    return {"p_home": "N/A", "p_draw": "N/A", "p_away": "N/A", "p_advance_a": "N/A"}
