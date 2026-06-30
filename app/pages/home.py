"""
首页概览 — 项目简介 + 夺冠高亮 + 数据概览 (1,2,7,8)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(results, team_map, team_ratings, groups, n_sim):
    # ── 1. 项目标题与简介 ──
    st.markdown('<div class="main-title">🏆 世界杯冠军预测 Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">'
        '基于五维度球队评分 + 泊松模型 + 蒙特卡洛模拟 | '
        '可解释 · 可视化 · 端到端自动化'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── 7. 冠军预测高亮展示 ──
    if results:
        top = results[0]
        top_name = top.team_name or top.team_id

        st.markdown("---")
        col_champ, col_stats = st.columns([1, 2])

        with col_champ:
            st.markdown(f"""
            <div class="champion-card">
                <div style="font-size:2.5rem;">🏆</div>
                <div class="champion-team">{top_name}</div>
                <div class="champion-prob">夺冠概率 <b>{top.champion_prob:.1%}</b></div>
                <div style="font-size:0.8rem;color:#555;">
                95% CI: [{top.ci_low:.1%}, {top.ci_high:.1%}]
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_stats:
            # Top 指标卡片
            c1, c2, c3, c4 = st.columns(4)
            top3_prob = sum(r.champion_prob for r in results[:3])
            with c1:
                st.markdown(f'<div class="metric-box"><div class="metric-value">{top3_prob:.1%}</div>'
                            f'<div class="metric-label">Top-3 合计概率</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-box"><div class="metric-value">{n_sim:,}</div>'
                            f'<div class="metric-label">蒙特卡洛模拟</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-box"><div class="metric-value">{len(team_ratings)}</div>'
                            f'<div class="metric-label">参赛球队</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="metric-box"><div class="metric-value">{len(groups)}</div>'
                            f'<div class="metric-label">小组数量</div></div>', unsafe_allow_html=True)

    # ── 2. 数据概览 ──
    st.markdown("---")
    st.subheader("📋 数据概览")

    tab1, tab2 = st.tabs(["🏅 夺冠排行", "📊 评分明细"])

    with tab1:
        cols = st.columns([1, 4, 2, 2, 2])
        cols[0].markdown("**#**")
        cols[1].markdown("**球队**")
        cols[2].markdown("**夺冠概率**")
        cols[3].markdown("**95% CI**")
        cols[4].markdown("**评分**")

        for i, r in enumerate(results[:10], 1):
            name = r.team_name or r.team_id
            c1, c2, c3, c4, c5 = st.columns([1, 4, 2, 2, 2])
            c1.markdown(f"{i}")
            c2.markdown(f"**{name}**")
            c3.progress(min(r.champion_prob * 5, 1.0), text=f"{r.champion_prob:.1%}")
            c4.markdown(f"[{r.ci_low:.1%}, {r.ci_high:.1%}]")
            c5.markdown(f"{r.overall_rating:.1f}")

    with tab2:
        # 评分柱状图
        top_teams = results[:8]
        df_plot = pd.DataFrame({
            "球队": [r.team_name or r.team_id for r in top_teams],
            "夺冠概率": [r.champion_prob * 100 for r in top_teams],
            "综合评分": [r.overall_rating for r in top_teams],
        })
        fig = px.bar(
            df_plot, x="球队", y="夺冠概率",
            color="综合评分", color_continuous_scale="Blues",
            text_auto=".1f",
            labels={"夺冠概率": "夺冠概率 (%)"},
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(height=380, margin=dict(l=20, r=20, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # ── 8. 推理过程解释面板 ──
    st.markdown("---")
    st.subheader("🧠 推理过程说明")

    with st.expander("📖 点击展开: 模型如何得出预测结果", expanded=False):
        tab_explain, tab_flow = st.tabs(["⚙️ 方法论", "🔄 数据流"])

        with tab_explain:
            st.markdown("""
            ### 预测模型架构

            **Layer 0 — 球队评分引擎 (五维度加权)**
            | 维度 | 权重 | 说明 |
            |------|------|------|
            | 🏆 历史底蕴 | 20% | 世界杯冠军/亚军/四强次数，1980年前成绩衰减 |
            | 📊 FIFA排名 | 30% | FIFA排名线性归一化 + ELO评分加权(7:3) |
            | ⚔️ 攻防效率 | 20% | 近20场场均进球/失球 + 对手强度修正 |
            | 👥 球员班底 | 15% | FIFA游戏评分(首发60%+替补40%)归一化 |
            | 📈 近期状态 | 15% | 近10场胜率 + 连胜/连败动量修正 |

            **Layer 1 — 单场预测 (独立泊松模型)**
            - λ = 联赛均值 × 攻击力(A) × 防守力(B) × 东道主加成
            - P(胜/平/负) 从两个独立泊松分布求和导出

            **Layer 2 — 蒙特卡洛模拟**
            - N 次完整世界杯模拟，每次独立采样比分
            - 淘汰赛三阶段: 90分钟 → 加时(×0.33) → 点球(55%)
            """)

        with tab_flow:
            st.markdown("""
            ```
            数据加载 (40支球队)
                ↓
            build_team_snapshots()  →  历史+排名+攻防+状态
                ↓
            rate_all_teams()        →  五维度评分 (0-100)
                ↓
            simulate_group()        →  小组赛积分 + 出线队
                ↓
            simulate_knockout_3stage() → 90min→加时→点球
                ↓
            run_monte_carlo(N)      →  统计夺冠次数 → 概率
                ↓
            Wilson CI               →  95% 置信区间
            ```
            """)
