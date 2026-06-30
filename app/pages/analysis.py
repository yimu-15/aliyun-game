"""
球队实力榜 + 小组赛预测 (3,4)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px


def render(results, team_map, team_ratings, groups):
    st.markdown('<div class="main-title">📊 球队实力分析</div>', unsafe_allow_html=True)

    # ── 3. 球队实力榜/评分榜 ──
    tab_rank, tab_radar, tab_group = st.tabs(["🏅 实力排行", "🎯 评分雷达", "📋 小组赛预测"])

    with tab_rank:
        st.subheader("综合实力排行榜")

        # 按综合评分排序
        sorted_teams = sorted(team_ratings, key=lambda t: t.overall, reverse=True)

        # 表格 + 进度条
        cols = st.columns([1, 3, 3, 2, 2, 2, 2])
        cols[0].markdown("**#**")
        cols[1].markdown("**球队**")
        cols[2].markdown("**综合**")
        cols[3].markdown("**FIFA#**")
        cols[4].markdown("**历史**")
        cols[5].markdown("**攻防**")
        cols[6].markdown("**状态**")

        for i, t in enumerate(sorted_teams[:15], 1):
            name = t.team_name or t.team_id
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 3, 3, 2, 2, 2, 2])
            c1.markdown(f"{i}")
            c2.markdown(f"**{name}**")
            c3.progress(t.overall / 50, text=f"{t.overall:.1f}")
            c4.markdown(f"#{t.fifa_rank}")
            c5.markdown(f"{t.historical:.0f}")
            c6.markdown(f"{t.attack_defense:.0f}")
            c7.markdown(f"{t.recent_form:.0f}")

        # 评分分布图
        st.markdown("---")
        df_scores = pd.DataFrame({
            "球队": [(t.team_name or t.team_id) for t in sorted_teams[:10]],
            "历史底蕴": [t.historical for t in sorted_teams[:10]],
            "FIFA排名": [t.strength for t in sorted_teams[:10]],
            "攻防效率": [t.attack_defense for t in sorted_teams[:10]],
            "球员班底": [t.player_quality for t in sorted_teams[:10]],
            "近期状态": [t.recent_form for t in sorted_teams[:10]],
        })

        fig = px.bar(
            df_scores.melt(id_vars="球队", var_name="维度", value_name="得分"),
            x="球队", y="得分", color="维度",
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=10, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with tab_radar:
        st.subheader("五维度评分雷达图")

        selected_teams = st.multiselect(
            "选择对比球队 (最多4支)",
            options=[(t.team_name or t.team_id) for t in team_ratings],
            default=[(team_ratings[0].team_name or team_ratings[0].team_id),
                     (team_ratings[1].team_name or team_ratings[1].team_id)],
            max_selections=4,
        )

        if selected_teams:
            fig = go.Figure()
            categories = ["历史底蕴", "FIFA排名", "攻防效率", "球员班底", "近期状态"]
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

            for idx, name in enumerate(selected_teams):
                t = next((t for t in team_ratings if (t.team_name or t.team_id) == name), None)
                if t:
                    vals = [t.historical, t.strength, t.attack_defense,
                            t.player_quality, t.recent_form]
                    fig.add_trace(go.Scatterpolar(
                        r=vals + [vals[0]],
                        theta=categories + [categories[0]],
                        fill="toself",
                        name=name,
                        line_color=colors[idx % len(colors)],
                    ))

            fig.update_layout(
                polar=dict(radialaxis=dict(range=[0, 55])),
                height=450,
                margin=dict(l=40, r=40, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── 4. 小组赛预测 ──
    with tab_group:
        st.subheader("小组赛预测结果")

        for group_name, team_ids in groups.items():
            with st.expander(f"🏁 {group_name} 组", expanded=len(groups) <= 4):
                group_teams = [team_map.get(tid) for tid in team_ids if tid in team_map]
                if len(group_teams) < 2:
                    st.info("该组球队不足")
                    continue

                # 模拟一轮小组赛
                st.markdown(f"**{group_name} 组** ({len(group_teams)} 队)")

                rows = []
                for i in range(len(group_teams)):
                    for j in range(i + 1, len(group_teams)):
                        a, b = group_teams[i], group_teams[j]
                        from models.group_stage import predict_match
                        pred = predict_match(a, b)
                        rows.append({
                            "对阵": f"{a.team_id} vs {b.team_id}",
                            "主胜": f"{pred.p_home_win:.1%}",
                            "平局": f"{pred.p_draw:.1%}",
                            "客胜": f"{pred.p_away_win:.1%}",
                            "最可能比分": pred.best_score,
                        })

                df_group = pd.DataFrame(rows)
                st.dataframe(df_group, use_container_width=True, hide_index=True)

                # 积分模拟
                from models.group_stage import simulate_group
                rng = np.random.RandomState(42)
                sim_result = simulate_group(group_teams, group_name, ["CAN","MEX","USA"], rng)
                st.caption("📊 一次模拟积分榜 (实际结果随机):")
                for s in sim_result["standings"]:
                    nm = team_map.get(s["team_id"])
                    nm_str = (nm.team_name or s["team_id"]) if nm else s["team_id"]
                    st.caption(f"  {s['rank']}. {nm_str}  {s['pts']}pts  "
                               f"GF:{s['gf']} GA:{s['ga']} GD:{s['gd']}")
