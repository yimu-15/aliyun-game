"""
比分预测 + 推理过程解释面板 (6,8)
"""

import streamlit as st
import plotly.graph_objects as go
from models.group_stage import predict_match


def render(results, team_map, team_ratings):
    st.markdown('<div class="main-title">🔍 单场比分预测</div>', unsafe_allow_html=True)

    # 球队选择
    team_options = [(t.team_name or t.team_id) for t in team_ratings]
    col1, col2 = st.columns(2)
    with col1:
        sel_a = st.selectbox("🏠 主队", team_options, index=0)
    with col2:
        sel_b = st.selectbox("🚩 客队", team_options,
                             index=min(1, len(team_options)-1))

    ta = next((t for t in team_ratings if (t.team_name or t.team_id) == sel_a), None)
    tb = next((t for t in team_ratings if (t.team_name or t.team_id) == sel_b), None)

    if not ta or not tb:
        st.warning("请选择两支不同的球队")
        return

    # ── 6. 比分预测 ──
    pred = predict_match(ta, tb)

    st.markdown("---")
    st.subheader(f"⚽ {sel_a} vs {sel_b}")

    # 胜平负概率条
    max_prob = max(pred.p_home_win, pred.p_draw, pred.p_away_win)
    c_a, c_d, c_b = st.columns([5, 3, 5])
    with c_a:
        color_a = "#1f77b4" if pred.p_home_win == max_prob else "#e0e0e0"
        st.markdown(f"### {sel_a} 胜")
        st.markdown(f"<span style='font-size:2rem;color:{color_a};font-weight:700;'>{pred.p_home_win:.1%}</span>",
                    unsafe_allow_html=True)
        st.progress(pred.p_home_win)
    with c_d:
        st.markdown("### 平")
        st.markdown(f"<span style='font-size:1.5rem;color:#888;'>{pred.p_draw:.1%}</span>",
                    unsafe_allow_html=True)
        st.progress(pred.p_draw)
    with c_b:
        color_b = "#d62728" if pred.p_away_win == max_prob else "#e0e0e0"
        st.markdown(f"### {sel_b} 胜")
        st.markdown(f"<span style='font-size:2rem;color:{color_b};font-weight:700;'>{pred.p_away_win:.1%}</span>",
                    unsafe_allow_html=True)
        st.progress(pred.p_away_win)

    # 期望进球 + 最可能比分
    col1, col2, col3 = st.columns(3)
    col1.metric(f"⚽ {sel_a} xG", f"{pred.lam_home:.2f}")
    col2.metric("最可能比分", pred.best_score)
    col3.metric(f"⚽ {sel_b} xG", f"{pred.lam_away:.2f}")

    # ── 8. 推理过程解释面板 ──
    st.markdown("---")
    st.subheader("🧠 推理过程解释")

    tab_factor, tab_rating, tab_calc = st.tabs(["📊 胜负因子", "📈 评分对比", "🔢 计算过程"])

    with tab_factor:
        st.markdown("### 胜负关键因子分析")

        factors_data = [
            {"因子": "FIFA排名", ta_name: f"{ta.strength:.1f}", tb_name: f"{tb.strength:.1f}",
             "优势方": ta_name if ta.strength > tb.strength else tb_name},
            {"因子": "攻防效率", ta_name: f"{ta.attack_defense:.1f}", tb_name: f"{tb.attack_defense:.1f}",
             "优势方": ta_name if ta.attack_defense > tb.attack_defense else tb_name},
            {"因子": "历史底蕴", ta_name: f"{ta.historical:.1f}", tb_name: f"{tb.historical:.1f}",
             "优势方": ta_name if ta.historical > tb.historical else tb_name},
            {"因子": "近期状态", ta_name: f"{ta.recent_form:.1f}", tb_name: f"{tb.recent_form:.1f}",
             "优势方": ta_name if ta.recent_form > tb.recent_form else tb_name},
            {"因子": "球员班底", ta_name: f"{ta.player_quality:.1f}", tb_name: f"{tb.player_quality:.1f}",
             "优势方": ta_name if ta.player_quality > tb.player_quality else tb_name},
        ]

        # 瀑布图展示贡献
        diffs = []
        cumulative = 0.5
        factor_names = []
        for f in factors_data:
            factor_names.append(f["因子"])
            if f["优势方"] == ta_name:
                diff = min((getattr(ta, {"FIFA排名":"strength","攻防效率":"attack_defense",
                    "历史底蕴":"historical","近期状态":"recent_form","球员班底":"player_quality"}.get(f["因子"],"strength"))
                    - getattr(tb, {"FIFA排名":"strength","攻防效率":"attack_defense",
                    "历史底蕴":"historical","近期状态":"recent_form","球员班底":"player_quality"}.get(f["因子"],"strength"))
                    ) * 0.005, 0.08)
            else:
                diff = -min(abs(getattr(ta, {"FIFA排名":"strength","攻防效率":"attack_defense",
                    "历史底蕴":"historical","近期状态":"recent_form","球员班底":"player_quality"}.get(f["因子"],"strength"))
                    - getattr(tb, {"FIFA排名":"strength","攻防效率":"attack_defense",
                    "历史底蕴":"historical","近期状态":"recent_form","球员班底":"player_quality"}.get(f["因子"],"strength"))
                    ) * 0.005, 0.08)
            diffs.append(diff)

        fig = go.Figure(go.Waterfall(
            name="胜率因子",
            orientation="v",
            measure=["absolute"] + ["relative"] * 5,
            x=["基准胜率"] + factor_names,
            y=[0.5] + diffs,
            text=[f"{0.5:.2f}"] + [f"{d:+.3f}" for d in diffs],
            connector={"line": {"color": "#ccc"}},
            increasing={"marker": {"color": "#1f77b4"}},
            decreasing={"marker": {"color": "#d62728"}},
        ))
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20),
                          yaxis=dict(range=[0.3, max(0.65, 0.5+sum(diffs)+0.05)]))
        st.plotly_chart(fig, use_container_width=True)

        st.caption("💡 绿色=对主队有利 | 红色=对客队有利 | 解释: 各因子对胜率的边际贡献")

    with tab_rating:
        st.markdown("### 两队评分对比")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**{sel_a}**")
            st.metric("综合评分", f"{ta.overall:.1f}")
            st.metric("FIFA排名", f"#{ta.fifa_rank}")
            st.progress(ta.strength / 50, text=f"排名评分: {ta.strength:.1f}")
            st.progress(ta.attack_defense / 50, text=f"攻防: {ta.attack_defense:.1f}")
            st.progress(ta.recent_form / 50, text=f"状态: {ta.recent_form:.1f}")
        with col_b:
            st.markdown(f"**{sel_b}**")
            st.metric("综合评分", f"{tb.overall:.1f}")
            st.metric("FIFA排名", f"#{tb.fifa_rank}")
            st.progress(tb.strength / 50, text=f"排名评分: {tb.strength:.1f}")
            st.progress(tb.attack_defense / 50, text=f"攻防: {tb.attack_defense:.1f}")
            st.progress(tb.recent_form / 50, text=f"状态: {tb.recent_form:.1f}")

    with tab_calc:
        st.markdown("### 🔢 计算过程明细")
        st.markdown(f"""
        **期望进球 (λ) 计算:**

        | 参数 | {sel_a} | {sel_b} |
        |------|--------|--------|
        | 攻击力系数 | {ta.attack_factor:.3f} | {tb.attack_factor:.3f} |
        | 对手防守系数 | {tb.defense_factor:.3f} | {ta.defense_factor:.3f} |
        | 联赛均值 | {1.32} | {1.32} |
        | **期望进球 λ** | **{pred.lam_home:.3f}** | **{pred.lam_away:.3f}** |

        **胜/平/负概率** (从泊松分布求和):
        - P({sel_a}胜) = Σ P(λ₁=i) × P(λ₂=j) for i > j  → **{pred.p_home_win:.1%}**
        - P(平局) = Σ P(λ₁=i) × P(λ₂=j) for i = j  → **{pred.p_draw:.1%}**
        - P({sel_b}胜) = Σ P(λ₁=i) × P(λ₂=j) for i < j  → **{pred.p_away_win:.1%}**
        """)
